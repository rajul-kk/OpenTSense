"""G77 case sets (DRAFT gate, not registered): fresh draws of G84's construction on two stacks and three noise levels.

G77 needs case sets its bars were not tuned on (its pilot used G84's, seed 84), the noise level swept (UPRE and the
discrepancy rule depend on sigma, GCV does not) and at least one stack besides G84's (G77 draft, open choice 1).

Construction: G84's (`gates/g84/make_cases.py`, registered, so not edited), generalised over the stack:
- 3d: the G71 3D stack, TPU die on top, CPU die buried; 10 x 10 power bins and 8 sensors per die (as G84).
- 25d: the G71 2.5D stack, CPU and TPU chiplets side by side on one layer (CPU left, TPU right, as G71's maps);
  10 x 11 bins (6 x 8 cells, since 88 columns do not divide by 10) and 16 sensors, so both stacks have 16 sensors.
Power per case as G84: a G81b program segment drives the CPU block, a seeded TPU workload (W1-W3, x U[0.9, 1.1])
drives the TPU block, and G71's background power on the inactive cells. Splits by program, seeded. One temperature
set per stack and one standard-normal noise draw per stack, scaled by each sigma (common random numbers), so the
noise levels differ only in sigma. Both stacks use the same seed, so they share the program split and TPU draws.

Copy check: with G84's settings (`--reproduce-g84`: seed 84, 3d, noise 0.1) the output must equal G84's case set
(sha256 in `gates/g84/record/result.json`), so the generalisation cannot drift from G84 unnoticed.

Usage (from the repo root): python gates/g77/make_cases.py <out dir> [--seed 77] [--stacks 3d,25d] [--noise 0.01,0.05,0.1]
                            python gates/g77/make_cases.py <out dir> --reproduce-g84
"""
import argparse
import json
import os
import sys
import tempfile

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as sla

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from opentsense.bench.cases import CaseSet  # noqa: E402
from opentsense.estimate.placement import uniform_grid  # noqa: E402
from opentsense.stack import model, to_pact  # noqa: E402
from opentsense.thermal import response  # noqa: E402

G71 = os.path.join(ROOT, "gates", "g71")
SEGS = 20
CPU_BLOCK_W, TPU_BLOCK_W = 1.0719, 6.9360          # G71 seed-0 block powers, as G84
DARK_CELL_W = 1.25e-4                               # G71: 0.05 W/mm^2 on 50 um cells
# per stack: config and G71 run folder; the active-block mask and background mask in G71's maps (None: every
# inactive cell, G84's form); bins (rows, cols) and sensors per die; G71's seed-0 map per die (plumbing); buried dies
STACKS = {
    "3d": dict(yaml="g71_3d.yaml", run="3d", act="act3", dark=None, bins=(10, 10), sensors=8,
               seed0={"top": "tpu_s0", "bot": "cpu_s0"}, buried={"bot"}),
    "25d": dict(yaml="g71_25d.yaml", run="25d", act="act25", dark="dark25", bins=(10, 11), sensors=16,
                seed0={"chiplets": "m25_s0"}, buried=set()),
}


def factor(cfg):
    stack = model.load(os.path.join(ROOT, "configs", "stacks", cfg["yaml"]))
    nx, ny = stack.grid
    with tempfile.TemporaryDirectory() as td:
        _, src = to_pact.write(stack, {d.name: np.zeros((ny, nx)) for d in stack.dies}, td)
    A = sp.load_npz(os.path.join(G71, f"runs/main/{cfg['run']}/operator/pact.A.npz")).tocsc()
    lu = sla.splu(A, permc_spec="MMD_AT_PLUS_A", diag_pivot_thresh=0.001, options=dict(Fact="DOFACT", Equil=False, SymmetricMode=True))
    dies = [d.name for d in stack.dies]

    def solve(powers):
        """powers: list of {die: (ny, nx) W} -> (n, D, ny, nx) rise."""
        B = np.zeros((A.shape[0], len(powers)))
        for j, p in enumerate(powers):
            r = response.rhs(stack, p, src); B[:len(r), j] = r
        X = lu.solve(B)
        out = np.zeros((len(powers), len(dies), ny, nx))
        for i, d in enumerate(dies):
            out[:, i] = X[src[d] * nx * ny:(src[d] + 1) * nx * ny].T.reshape(-1, ny, nx)[:, ::-1]
        return out
    return stack, dies, solve


def resample(M, n):
    """Area-weighted resample of a square map M to (n, n), keeping its total (as G84)."""
    k = M.shape[0]
    e = np.kron(M, np.ones((n, n))) / (n * n)
    return e.reshape(n, k, n, k).sum((1, 3))


def blocks(act):
    """(row slice, col slice) of each active block of a mask, left to right."""
    from scipy import ndimage
    lab, n = ndimage.label(act)
    out = []
    for i in range(1, n + 1):
        (r0, c0), (r1, c1) = np.argwhere(lab == i).min(0), np.argwhere(lab == i).max(0) + 1
        out.append((slice(r0, r1), slice(c0, c1)))
    return sorted(out, key=lambda b: b[1].start)


def build(stack_name, seed, noises):
    """({noise: CaseSet}, info) for one stack."""
    cfg = STACKS[stack_name]
    rng = np.random.default_rng(seed)
    stack, dies, solve = factor(cfg)
    nx, ny = stack.grid
    Z = np.load(os.path.join(G71, "inputs", "maps.npz"))
    act = Z[cfg["act"]]
    dark = np.where(act, 0.0, 0.4 / (~act).sum()) if cfg["dark"] is None else np.where(Z[cfg["dark"]], DARK_CELL_W, 0.0)
    blk = blocks(act)
    bs = blk[0][0].stop - blk[0][0].start
    by, bx = cfg["bins"]

    T0 = solve([{d: Z[cfg["seed0"][d]] for d in dies}])[0]
    F = np.load(os.path.join(G71, f"runs/main/{cfg['run']}_fields.npz"))
    plumb = {d: float(np.abs(T0[i] - F[f"s0_{d}_pact"]).max()) for i, d in enumerate(dies)}
    print(stack_name, "plumbing vs G71 PACT (max |dT| K):", plumb, flush=True)

    g81b = json.load(open(os.path.join(ROOT, "gates/g81b/record/result.json")))["programs"]
    progs = sorted(p for p in g81b if p != "idle_pass1" and "dyn_W" in g81b[p])
    med = np.median([g81b[p]["dyn_W"]["mean"] for p in progs])
    tl = {p: np.loadtxt(os.path.join(ROOT, f"gates/g81b/runs/main/{p}/timeline.csv"), delimiter=",")[:, 1:] for p in progs}
    tz = np.load(os.path.join(ROOT, "gates/g72/runs/main/maps.npz"))
    tpu = {w: resample(tz[f"tpu_{w}"], bs) for w in ("W1", "W2", "W3")}
    tpu_rel = {w: tpu[w].sum() / tpu["W1"].sum() for w in tpu}

    others = [p for p in progs if p != "idle"]
    order = rng.permutation(others)
    split_of = {p: "train" for p in order[:11]} | {p: "cal" for p in order[11:15]} | {p: "test" for p in order[15:19]} | {"idle": "train"}

    def put(M, b, block):
        out = M.copy(); out[b] += block; return out

    powers, P_bins, meta = [], [], []
    for p in progs:
        X = tl[p]
        mean_tog = X.sum(1).mean()
        for s in np.array_split(np.arange(len(X)), SEGS):
            share = X[s].sum(0).reshape(4, 4)
            share = share / share.sum() if share.sum() > 0 else np.full((4, 4), 1 / 16)   # idle asleep: 0 W
            cpu_W = CPU_BLOCK_W * g81b[p]["dyn_W"]["mean"] / med * X[s].sum(1).mean() / mean_tog
            cpu_block = np.kron(share, np.ones((bs // 4, bs // 4))) / (bs // 4) ** 2 * cpu_W
            w = ("W1", "W2", "W3")[rng.integers(3)]
            tpu_block = tpu[w] / tpu[w].sum() * TPU_BLOCK_W * tpu_rel[w] * rng.uniform(0.9, 1.1)
            if stack_name == "3d":
                pw = {"top": put(dark, blk[0], tpu_block), "bot": put(dark, blk[0], cpu_block)}
            else:
                pw = {"chiplets": put(put(dark, blk[0], cpu_block), blk[1], tpu_block)}
            powers.append(pw)
            P_bins.append([pw[d].reshape(by, ny // by, bx, nx // bx).sum((1, 3)).ravel() for d in dies])
            meta.append((p, w))
    print(f"{stack_name}: {len(powers)} cases from {len(progs)} programs; solving", flush=True)
    T = np.concatenate([solve(powers[k:k + 100]) for k in range(0, len(powers), 100)])

    hy, hx = ny // by, nx // bx
    basis = []
    for d in dies:
        for b in range(by * bx):
            M = np.zeros((ny, nx)); bi, bj = divmod(b, bx)
            M[bi * hy:(bi + 1) * hy, bj * hx:(bj + 1) * hx] = 1.0 / (hy * hx)
            basis.append({dd: (M if dd == d else np.zeros((ny, nx))) for dd in dies})
    R = np.concatenate([solve(basis[k:k + 100]) for k in range(0, len(basis), 100)])

    sens = np.concatenate([[(i, *divmod(int(s), nx)) for s in uniform_grid((ny, nx), cfg["sensors"], offset=0.5)]
                           for i in range(len(dies))])
    group = np.array([m[0] for m in meta]); split = np.array([split_of[g] for g in group])
    common = dict(T=T.astype(np.float32), P=np.array(P_bins, np.float32), R=R.astype(np.float32), sensors=sens,
                  split=split, group=group, tag=np.where(split == "test", "unseen-workload", "seen-group"),
                  tpu_workload=np.array([m[1] for m in meta]), dies=np.array(dies),
                  buried=np.array([d in cfg["buried"] for d in dies]), cell_um=float(stack.size_um[0] / nx),
                  stack_id=stack.name)
    # rng.normal(0, s) is 0 + s * standard_normal, so with one sigma this equals G84's draw bit for bit
    z = rng.standard_normal((len(T), len(sens)))
    clean = T[:, sens[:, 0], sens[:, 1], sens[:, 2]]
    sets = {sigma: CaseSet(dict(common, readings=clean + (0 + sigma * z), noise_K=sigma)) for sigma in noises}
    info = {"stack": stack_name, "seed": seed, "cases": len(T), "noise_K": list(noises), "plumbing_max_dT_K": plumb,
            "split": {s: int((split == s).sum()) for s in ("train", "cal", "test")},
            "programs_by_split": {s: sorted(p for p, v in split_of.items() if v == s) for s in ("train", "cal", "test")},
            "sensors": int(len(sens)), "bins_per_die": by * bx,
            "peak_rise_K": {d: [float(T[:, i].max((1, 2)).min()), float(T[:, i].max((1, 2)).max())] for i, d in enumerate(dies)}}
    return sets, info


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("out")
    ap.add_argument("--seed", type=int, default=77)
    ap.add_argument("--stacks", default="3d,25d")
    ap.add_argument("--noise", default="0.01,0.05,0.1", help="sensor noise sigmas, K")
    ap.add_argument("--reproduce-g84", action="store_true")
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    if a.reproduce_g84:
        want = json.load(open(os.path.join(ROOT, "gates/g84/record/result.json")))["case_set"]["sha256"]
        got = build("3d", 84, [0.1])[0][0.1].sha256()
        print("G84 reproduction:", "identical" if got == want else f"DIFFERS ({got} vs {want})")
        return 0 if got == want else 1
    if a.seed == 84:
        raise SystemExit("seed 84 is G84's pilot set, already seen; pick another")
    noises = [float(x) for x in a.noise.split(",")]
    if not all(s > 0 for s in noises) or len({f"{s:g}" for s in noises}) != len(noises):
        raise SystemExit("noise levels must be positive and distinct")
    index = {}
    for name in a.stacks.split(","):
        sets, info = build(name, a.seed, noises)
        info["files"] = {}
        for sigma, cs in sets.items():
            f = os.path.join(a.out, f"cases_{name}_noise{sigma:g}.npz")
            cs.save(f)
            info["files"][f"{sigma:g}"] = {"path": os.path.basename(f), "sha256": cs.sha256()}
        index[name] = info
        print(json.dumps(info, indent=1), flush=True)
    json.dump(index, open(os.path.join(a.out, "cases.json"), "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
