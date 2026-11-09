"""G93a: three thermal solvers (3D-ICE, PACT, HotSpot) and the extended stack format. See registration.md.
(a) regression of 3D-ICE and PACT against G71's stored fields; (b) HotSpot vs 3D-ICE and vs PACT on G71's stacks;
(c) all three pairs on two new configs (2.5D with underfill regions, 3D with a bottom sink). Extras: one node per
layer, a refined mesh on the 3D stack, wall times.
Usage (inside opentsense:g93a): python gates/g93a/run.py <out dir>
"""
import copy
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, ROOT)
from opentsense import manifest  # noqa: E402
from opentsense.stack import model  # noqa: E402
from opentsense.thermal.run import run_3dice, run_hotspot, run_pact  # noqa: E402

SEEDS = range(4)
BAR = dict(dpeak_K=1.0, dpeak_rel=0.04, rms_rel=0.02, regress_K=1e-9)
G71 = os.path.join(ROOT, "gates", "g71")
# name: (config, {die: map key}, part, G71 fields file or None)
STACKS = {
    "single": ("g71_single.yaml", {"die0": "tpu"}, "ab", "single_fields.npz"),
    "3d": ("g71_3d.yaml", {"top": "tpu", "bot": "cpu"}, "ab", "3d_fields.npz"),
    "25d": ("g71_25d.yaml", {"chiplets": "m25"}, "ab", "25d_fields.npz"),
    "25d_regions": ("g93a_25d_regions.yaml", {"chiplets": "m25"}, "c", None),
    "3d_bottom": ("g93a_3d_bottom.yaml", {"top": "tpu", "bot": "cpu"}, "c", None),
}
SOLVERS = {"ice": run_3dice, "pact": run_pact, "hs": run_hotspot}


def pair(a, b):
    """G71's metrics, a = reference (3D-ICE where it is in the pair)."""
    d = abs(a.max() - b.max())
    rms = float(np.sqrt(((a - b) ** 2).mean()))
    return dict(a_peak=float(a.max()), b_peak=float(b.max()), dpeak=float(d), dpeak_rel=float(d / a.max()), rms=rms,
                rms_rel=rms / float(a.mean()), max_abs=float(np.abs(a - b).max()))


def ok(m):
    return m["dpeak"] <= BAR["dpeak_K"] and m["dpeak_rel"] <= BAR["dpeak_rel"] and m["rms_rel"] <= BAR["rms_rel"]


def solve_all(stack, P, out):
    T, t = {}, {}
    for k, f in SOLVERS.items():
        t0 = time.time()
        T[k] = {d: v - stack.ambient_K for d, v in f(stack, P, os.path.join(out, k)).items()}
        t[k] = time.time() - t0
    return T, t


def main(out):
    os.makedirs(out, exist_ok=True)
    Z = np.load(os.path.join(G71, "inputs", "maps.npz"))
    res, t_start = {"bar": BAR, "stacks": {}}, time.time()
    pairs_b = (("ice", "hs"), ("pact", "hs"))
    pairs_c = (("ice", "pact"), ("ice", "hs"), ("pact", "hs"))
    for name, (cfg, dies, part, g71f) in STACKS.items():
        stack = model.load(os.path.join(ROOT, "configs", "stacks", cfg))
        ref = np.load(os.path.join(G71, "runs", "main", g71f)) if g71f else None
        r = {"part": part, "cases": []}
        fields = {}
        pairs = pairs_b if part == "ab" else pairs_c
        for seed in SEEDS:
            P = {d: Z[f"{key}_s{seed}"] for d, key in dies.items()}
            T, t = solve_all(stack, P, os.path.join(out, name, f"s{seed}"))
            case = dict(seed=seed, wall_s=t, pairs={}, regress={})
            for d in dies:
                for a, b in pairs:
                    case["pairs"][f"{d} {a}-{b}"] = pair(T[a][d], T[b][d])
                if ref is not None:
                    case["regress"][d] = {k: float(np.abs(T[k][d] - ref[f"s{seed}_{d}_{k}"]).max()) for k in ("ice", "pact")}
                for k in SOLVERS:
                    fields[f"s{seed}_{d}_{k}"] = T[k][d]
            r["cases"].append(case)
            print(f"[{name}] seed {seed} " + json.dumps({k: (round(v['dpeak'], 4), round(v['rms_rel'], 5)) for k, v in case["pairs"].items()})
                  + (f" regress {json.dumps(case['regress'])}" if ref is not None else "") + f" t {json.dumps({k: round(v, 1) for k, v in t.items()})}", flush=True)
        # extras: one node per layer (seed 0); refined mesh for the 3D stack (seed 0)
        P0 = {d: Z[f"{key}_s0"] for d, key in dies.items()}
        s1 = copy.deepcopy(stack)
        for l in s1.layers:
            l.n_sub = 1
        T1, _ = solve_all(s1, P0, os.path.join(out, name, "coarse"))
        r["coarse_s0"] = {d: {k: float(T1[k][d].max()) for k in SOLVERS} for d in dies}
        if name == "3d":
            s2 = copy.deepcopy(stack)
            for l in s2.layers:
                l.n_sub *= 2
            T2, t2 = solve_all(s2, P0, os.path.join(out, name, "fine"))
            r["fine_s0"] = {d: {k: float(T2[k][d].max()) for k in SOLVERS} for d in dies}
            r["fine_s0_wall_s"] = t2
        # verdicts
        r["pairs_ok"] = all(ok(m) for c in r["cases"] for m in c["pairs"].values())
        r["worst"] = {k: max(m[k] for c in r["cases"] for m in c["pairs"].values()) for k in ("dpeak", "dpeak_rel", "rms_rel", "max_abs")}
        if ref is not None:
            r["regress_max"] = max(v for c in r["cases"] for dd in c["regress"].values() for v in dd.values())
            r["regress_ok"] = r["regress_max"] <= BAR["regress_K"]
        r["pass"] = r["pairs_ok"] and r.get("regress_ok", True)
        res["stacks"][name] = r
        np.savez_compressed(os.path.join(out, f"{name}_fields.npz"), **fields)
        print(f"[{name}] worst {json.dumps({k: round(v, 5) for k, v in r['worst'].items()})}"
              + (f" regress_max {r['regress_max']:.3g}" if ref is not None else "") + f" -> {'PASS' if r['pass'] else 'FAIL'}", flush=True)
        json.dump(res, open(os.path.join(out, "result.json"), "w"), indent=1)
    S = res["stacks"]
    res["a"] = all(S[n]["regress_ok"] for n in S if S[n]["part"] == "ab")
    res["b"] = all(S[n]["pairs_ok"] for n in S if S[n]["part"] == "ab")
    res["c"] = all(S[n]["pairs_ok"] for n in S if S[n]["part"] == "c")
    res["verdict"] = "PASS" if res["a"] and res["b"] and res["c"] else "FAIL"
    res["total_s"] = time.time() - t_start
    json.dump(res, open(os.path.join(out, "result.json"), "w"), indent=1)
    manifest.write(os.path.join(out, "manifest.json"))
    print("G93a:", res["verdict"], json.dumps({k: res[k] for k in "abc"}), flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
