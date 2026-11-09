"""G81d2: compare data-symbol addresses of the looped binaries with G51's originals.
Usage: python3 layout.py <out dir>         prints `pad mm=P,conv=P,mlp1=P` (P makes the shift one 4 KiB page)
       python3 layout.py <out dir> --check  exits 1 unless every DMA buffer of every binary moved by exactly 4096 bytes
The DMA buffers (the arrays Gemmini reads and writes) are what alignment affects. Small scalars and linker markers can
move by other amounts because alignment padding absorbs part of the shift; their shifts are printed, not checked.
"""
import re
import subprocess
import sys

O = sys.argv[1]
B = "/home/rajul/g51/chipyard/generators/gemmini/software/gemmini-rocc-tests/build"
PAIRS = {"mm": (f"{B}/bareMetalC/tiled_matmul_ws_perf-baremetal", f"{O}/bm/g81d_mm-baremetal"),
         "conv": (f"{B}/bareMetalC/conv_perf-baremetal", f"{O}/bm/g81d_conv-baremetal"),
         "mlp1": (f"{B}/mlps/mlp1-baremetal", f"{O}/mlps/g81d_mlp1-baremetal")}


def syms(path):
    """data symbols (.data/.sdata/.bss/.rodata, local or global) placed after .text, by name"""
    out = subprocess.run(["riscv64-unknown-elf-nm", "-n", path], capture_output=True, text=True, check=True).stdout
    d = {}
    for line in out.splitlines():
        p = line.split()
        if len(p) == 3 and p[1] in "bBdDrRsSgG" and "g81d" not in p[2] and int(p[0], 16) >= 0x80003000:
            d[p[2]] = int(p[0], 16)
    return d


BUF = {"mm": r"full_[ABCD]\.\d+$", "conv": r"heap\.\d+$", "mlp1": r"(weights|inter_results)\d$|input_mat$"}
ok, pads = True, {}
for k, (orig, new) in PAIRS.items():
    a, b = syms(orig), syms(new)
    common = sorted(set(a) & set(b))
    bufs = [s for s in common if re.search(BUF[k], s)]
    shifts = sorted({b[s] - a[s] for s in bufs})
    other = {s: b[s] - a[s] for s in common if s not in bufs}
    missing = sorted(set(a) ^ set(b))
    print(f"{k}: {len(bufs)} DMA buffers, shifts {shifts}; other symbols {other}; unmatched {missing}", file=sys.stderr)
    pads[k] = (4096 - shifts[0]) % 4096 if len(shifts) == 1 else None
    ok &= shifts == [4096] and not missing
if "--check" in sys.argv:
    print("LAYOUT_OK" if ok else "LAYOUT_MISMATCH"); sys.exit(0 if ok else 1)
assert all(v is not None for v in pads.values()), "data symbols moved by different amounts; padding cannot fix this"
print(",".join(f"{k}={v}" for k, v in pads.items()))
