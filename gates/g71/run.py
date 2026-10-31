"""G71: the same YAML stack in 3D-ICE and PACT agrees within 1 K; the response operator matches full solves.

For each stack (single die, two-die 3D, 2.5D) and each of the 4 G38 workload draws (seeds 0-3):
  - full 3D-ICE and full PACT solves of the per-die rise maps;
  - |dpeak| and RMS difference per die (3D-ICE is the reference for the relative bars).
Per stack, a response operator from PACT's own matrix: one basis column per active-block cell, plus one for the
uniform dark power of each die (an exact basis for these maps), compared with the PACT full solves.
Extras, not criteria: the operator with 100 um and 200 um bins, and the one-node-per-layer mesh (seed 0).
Usage (inside the image): python gates/g71/run.py <out dir>
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
from opentsense.thermal import response  # noqa: E402
from opentsense.thermal.run import run_3dice, run_pact  # noqa: E402

SEEDS = range(4)
CELL, DARK = 50.0, 0.05e-6
STACKS = {  # config, {die: (map key, active mask, dark mask)}
    "single": ("g71_single.yaml", {"die0": ("tpu", "act3", "dark3")}),
    "3d": ("g71_3d.yaml", {"top": ("tpu", "act3", "dark3"), "bot": ("cpu", "act3", "dark3")}),
    "25d": ("g71_25d.yaml", {"chiplets": ("m25", "act25", "dark25")}),
}
BAR = dict(dpeak_K=1.0, dpeak_rel=0.04, rms_rel=0.02, op_K=0.1)


def basis_for(stack, dies, Z):
    """Per-cell columns over each die's active block, plus that die's dark-power pattern. Returns
    (basis, index) with index[k] = (die, cell (i, j) or 'dark')."""
    nx, ny = stack.grid
    zero = {d: np.zeros((ny, nx)) for d in dies}
    basis, index = [], []
    for d, (_, act, dark) in dies.items():
        for i, j in zip(*np.nonzero(Z[act])):
            p = copy.deepcopy(zero); p[d][i, j] = 1.0; basis.append(p); index.append((d, (int(i), int(j))))
        p = copy.deepcopy(zero); p[d] = np.where(Z[dark], DARK * CELL * CELL, 0.0); basis.append(p); index.append((d, "dark"))
    return basis, index


def coeffs_for(power, dies, Z, index):
    c = np.array([power[d][cell] if cell != "dark" else 1.0 for d, cell in index])
    for d, (_, act, dark) in dies.items():   # the basis must reproduce the map exactly
        rebuilt = np.where(Z[dark], DARK * CELL * CELL, 0.0)
        rebuilt[Z[act]] = power[d][Z[act]]
        assert np.allclose(rebuilt, power[d], rtol=1e-12, atol=1e-18), f"{d}: power outside the basis"
    return c


def binned_error(R, index, dies, power, full, size):
    """Operator with size x size cell bins over the active blocks (uniform power within a bin)."""
    groups = {}
    for k, (d, cell) in enumerate(index):
        key = (d, "dark") if cell == "dark" else (d, cell[0] // size, cell[1] // size)
        groups.setdefault(key, []).append(k)
    T = 0.0
    for key, ks in groups.items():
        d = key[0]
        if key[1] == "dark":
            T = T + R[ks[0]]
        else:
            tot = sum(power[d][index[k][1]] for k in ks)
            T = T + tot * R[ks].mean(axis=0)
    return float(max(np.abs(T[i] - full[d]).max() for i, d in enumerate(dies)))


def coarse(stack):
    s = copy.deepcopy(stack)
    for l in s.layers:
        l.n_sub = 1
    return s


def main(out):
    os.makedirs(out, exist_ok=True)
    Z = np.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "inputs", "maps.npz"))
    res, t_start = {"bar": BAR, "stacks": {}}, time.time()
    for name, (cfg, dies) in STACKS.items():
        stack = model.load(os.path.join(ROOT, "configs", "stacks", cfg))
        amb = stack.ambient_K
        r = {"cases": [], "mesh": {l.name: l.n_sub for l in stack.layers}}
        fields = {}
        basis, index = basis_for(stack, dies, Z)
        t0 = time.time()
        R = response.build(stack, basis, os.path.join(out, name, "operator"))
        r["operator"] = dict(n_basis=len(basis), build_s=time.time() - t0)
        print(f"[{name}] operator: {len(basis)} columns in {time.time() - t0:.0f} s", flush=True)
        for seed in SEEDS:
            P = {d: Z[f"{key}_s{seed}"] for d, (key, _, _) in dies.items()}
            t0 = time.time(); ice = run_3dice(stack, P, os.path.join(out, name, f"s{seed}", "ice")); t1 = time.time()
            pact = run_pact(stack, P, os.path.join(out, name, f"s{seed}", "pact")); t2 = time.time()
            T_op = response.apply(R, coeffs_for(P, dies, Z, index))
            case = dict(seed=seed, ice_s=t1 - t0, pact_s=t2 - t1, power_W={d: float(P[d].sum()) for d in dies}, dies={})
            for i, d in enumerate(dies):
                a, b = ice[d] - amb, pact[d] - amb
                case["dies"][d] = dict(ice_peak=float(a.max()), pact_peak=float(b.max()), dpeak=float(abs(a.max() - b.max())),
                                       dpeak_rel=float(abs(a.max() - b.max()) / a.max()), rms=float(np.sqrt(((a - b) ** 2).mean())),
                                       ice_mean=float(a.mean()), rms_rel=float(np.sqrt(((a - b) ** 2).mean()) / a.mean()),
                                       argmax_same=bool(a.argmax() == b.argmax()), op_err=float(np.abs(T_op[i] - b).max()))
                fields[f"s{seed}_{d}_ice"], fields[f"s{seed}_{d}_pact"], fields[f"s{seed}_{d}_op"] = a, b, T_op[i]
            full = {d: pact[d] - amb for d in dies}
            case["op_binned_err"] = {f"{s * 50}um": binned_error(R, index, list(dies), P, full, s) for s in (2, 4)}
            r["cases"].append(case)
            print(f"[{name}] seed {seed}: " + json.dumps({d: {k: round(v, 4) if isinstance(v, float) else v for k, v in m.items()} for d, m in case["dies"].items()})
                  + f" binned {case['op_binned_err']}", flush=True)
        # extra: one node per layer (seed 0)
        P = {d: Z[f"{key}_s0"] for d, (key, _, _) in dies.items()}
        s1 = coarse(stack)
        ice1 = run_3dice(s1, P, os.path.join(out, name, "coarse", "ice")); pact1 = run_pact(s1, P, os.path.join(out, name, "coarse", "pact"))
        r["coarse_s0"] = {d: dict(ice_peak=float(ice1[d].max() - amb), pact_peak=float(pact1[d].max() - amb)) for d in dies}
        # verdict for this stack: every seed and die meets every bar
        ok = all(m["dpeak"] <= BAR["dpeak_K"] and m["dpeak_rel"] <= BAR["dpeak_rel"] and m["rms_rel"] <= BAR["rms_rel"] and m["op_err"] <= BAR["op_K"]
                 for c in r["cases"] for m in c["dies"].values())
        r["worst"] = {k: max(m[k] for c in r["cases"] for m in c["dies"].values()) for k in ("dpeak", "dpeak_rel", "rms_rel", "op_err")}
        r["pass"] = ok
        res["stacks"][name] = r
        np.savez_compressed(os.path.join(out, f"{name}_fields.npz"), **fields)
        print(f"[{name}] worst {json.dumps({k: round(v, 5) for k, v in r['worst'].items()})} -> {'PASS' if ok else 'FAIL'}", flush=True)
        json.dump(res, open(os.path.join(out, "result.json"), "w"), indent=1)
    res["verdict"] = "PASS" if all(s["pass"] for s in res["stacks"].values()) else "FAIL"
    res["total_s"] = time.time() - t_start
    json.dump(res, open(os.path.join(out, "result.json"), "w"), indent=1)
    manifest.write(os.path.join(out, "manifest.json"))
    print("G71:", res["verdict"], flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
