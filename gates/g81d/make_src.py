"""G81d: write looped copies of three Gemmini tests (G51's workloads) into an output folder.

Usage: python make_src.py <gemmini-rocc-tests dir> <out dir> <K_mm> <K_conv> <K_mlp1>

Each compute region (everything between the first cycle read and the final cycle read of the original test) is wrapped
in `for (g81d_it = 0; g81d_it < G81D_K; g81d_it++)` followed by `gemmini_fence()`. A cycle stamp is stored at the start of
every iteration and after the last one. Nothing is printed inside the loop (no CPU work between iterations beyond the
loop itself); the stamps are printed once at the end as `G81D_STAMP <i> <cycle>`. K is written into each source.
The originals are not modified. The edit is purely textual and asserted, so a changed upstream file fails loudly.
"""
import os
import sys

SRC, OUT = sys.argv[1], sys.argv[2]
KS = dict(zip(("g81d_mm.c", "g81d_conv.c", "g81d_mlp1.c"), map(int, sys.argv[3:6])))
# --stack (G81d2): the stamp array lives on main's stack, so no static data symbol moves. G81d's static array shifted
# conv's 4 MB `heap` from 8 bytes past a 64-byte boundary to aligned, and Gemmini then did 9% less DMA work.
STACK = "--stack" in sys.argv
# --pad mm=P,conv=P,mlp1=P (G81d2): P bytes of padding appended to .text, chosen by build.sh so that every data symbol
# lands exactly one 4 KiB page above its address in G51's binary (same offset within the page, so the same alignment).
PAD = {}
if "--pad" in sys.argv:
    PAD = {f"g81d_{k}.c": int(v) for k, v in (x.split("=") for x in sys.argv[sys.argv.index("--pad") + 1].split(","))}
os.makedirs(OUT, exist_ok=True)
if STACK:
    HDR = ("#define G81D_K @K@\n"
           "static void g81d_report(const uint64_t *s) { for (int i = 0; i <= G81D_K; i++) printf(\"G81D_STAMP %d %llu\\n\", i, "
           "(unsigned long long)s[i]); printf(\"G81D_DONE %d\\n\", G81D_K); }\n")
    OPEN = "uint64_t g81d_stamp[G81D_K + 1];\n    for (int g81d_it = 0; g81d_it < G81D_K; g81d_it++) {\n    g81d_stamp[g81d_it] = read_cycles();\n"
    CLOSE = "    gemmini_fence();\n    }\n    g81d_stamp[G81D_K] = read_cycles();\n    g81d_report(g81d_stamp);\n"
else:
    HDR = ("#define G81D_K @K@\n"
           "static uint64_t g81d_stamp[G81D_K + 1];\n"
           "static void g81d_report(void) { for (int i = 0; i <= G81D_K; i++) printf(\"G81D_STAMP %d %llu\\n\", i, "
           "(unsigned long long)g81d_stamp[i]); printf(\"G81D_DONE %d\\n\", G81D_K); }\n")
    OPEN = "for (int g81d_it = 0; g81d_it < G81D_K; g81d_it++) {\n    g81d_stamp[g81d_it] = read_cycles();\n"
    CLOSE = "    gemmini_fence();\n    }\n    g81d_stamp[G81D_K] = read_cycles();\n    g81d_report();\n"


def wrap(src, start, end, after_include, k):
    """start: text that begins the region (kept inside the loop); end: text just after the region (kept after)."""
    for t in (start, end, after_include):
        assert src.count(t) == 1, f"expected exactly one {t!r}"
    i, j = src.index(start), src.index(end)
    assert i < j
    src = src[:i] + OPEN + src[i:j] + CLOSE + src[j:]
    m = src.index(after_include) + len(after_include)
    return src[:m] + "\n" + HDR.replace("@K@", str(k)) + src[m:]


jobs = {
    # matmul: region = tiled_matmul_auto ... gemmini_fence(); the original's own `end` read follows
    "g81d_mm.c": ("bareMetalC/tiled_matmul_ws_perf.c", "    tiled_matmul_auto(", "    uint64_t end = read_cycles();",
                  '#include "include/gemmini_testutils.h"'),
    # conv: region = the second map_to_matmul if/else (the one holding tiled_matmul_auto / tiled_conv_auto); end read follows
    "g81d_conv.c": ("bareMetalC/conv_perf.c", "    if (map_to_matmul) {\n\n      tiled_matmul_auto(I, J, K,",
                    "    uint64_t end_gemmini = read_cycles();",
                    '#include "include/gemmini_testutils.h"'),
    # mlp1: region = all six layers; the per-layer cycle reads stay inside (last iteration's values are printed)
    "g81d_mlp1.c": ("mlps/mlp1.c", "    /* matmul number: 0 */", "    uint64_t overall_cycles = 0;",
                    '#include "parameters1.h"'),
}
for out, (src, start, end, inc) in jobs.items():
    text = open(os.path.join(SRC, src)).read()
    body = wrap(text, start, end, inc, KS[out])
    if PAD.get(out):
        body += f'\n__asm__(".pushsection .text\\n.space {PAD[out]}\\n.popsection");   /* G81d2 page-shift padding */\n'
    open(os.path.join(OUT, out), "w").write(body)
    print("wrote", out)
open(os.path.join(OUT, "parameters1.h"), "w").write(open(os.path.join(SRC, "mlps", "parameters1.h")).read())   # mlp1's data
