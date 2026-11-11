"""G81a dry analysis (not scored): per-net value changes in the dut scope of two VCDs (Icarus vs Verilator), same window."""
import sys
from collections import Counter


def load(p):
    stack, name_of, sig = [], {}, {}
    f = open(p, "rb")
    for raw in f:
        l = raw.decode(errors="replace")
        t = l.split()
        if not t: continue
        if t[0] == "$scope": stack.append(t[2])
        elif t[0] == "$upscope": stack.pop()
        elif t[0] == "$var":
            path = "/".join(stack)
            if path.endswith("tb/dut") and t[2] == "1":
                name_of.setdefault(t[3], []).append(t[4].lstrip("\\"))
        elif t[0] == "$enddefinitions": break
    cnt, last, steps = Counter(), {}, 0
    for raw in f:
        c = raw[:1]
        if c == b"#": steps += 1; continue
        if c in (b"0", b"1", b"x", b"z"):
            code = raw[1:].strip().decode(); v = c
            if code in name_of:
                if code in last and last[code] != v: cnt[code] += 1
                last[code] = v
    out = Counter()
    for code, names in name_of.items():
        for n in names: out[n] += cnt[code]
    return out, steps


a, sa = load(sys.argv[1]); b, sb = load(sys.argv[2])
common = set(a) & set(b)
ta, tb = sum(a[n] for n in common), sum(b[n] for n in common)
print(f"time steps: icarus {sa}, verilator {sb}; nets icarus {len(a)}, verilator {len(b)}, common {len(common)}")
print(f"toggles on common nets: icarus {ta}, verilator {tb}, ratio {tb / ta:.4f}")
diff = sorted(common, key=lambda n: a[n] - b[n], reverse=True)
print("most extra icarus toggles:", [(n, a[n], b[n]) for n in diff[:12]])
print("nets with icarus > verilator:", sum(a[n] > b[n] for n in common), " verilator > icarus:", sum(b[n] > a[n] for n in common))
print("only-icarus nets sample:", sorted(set(a) - set(b))[:10])
