"""G84 case set: the G71 3D stack (TPU die on top, CPU die buried) driven by G81b whole-program activity.

Physics: the steady rise is G^-1 P with G = PACT's own conductance matrix, captured in G71 (`../g71/runs/main/3d/
operator/pact.A.npz`; G71 checked the operator against full solves). The matrix is factorised once here.
Plumbing check first: G71's seed-0 power solved with this factorisation must equal G71's stored PACT fields.

Power (G38/G71 layout: 1 mm active block at (1, 1) mm on each 3 x 3 mm die, 0.05 W/mm^2 dark power elsewhere):
- CPU die (buried): each G81b program's toggle timeline (4 x 4 regions per 1,000 cycles) is cut into SEGS segments;
  a segment's region shares are spread over the active block, and its block power is 1.07 W (G71's CPU block) x the
  program's mean dynamic power / the suite median x the segment's toggles / the program's mean toggles.
- TPU die (top): G72's TPU maps W1, W2, W3 resampled onto the block, scaled to 6.94 W (G71's TPU block) x their total
  relative to W1, times a seeded uniform factor in [0.9, 1.1]; the workload is drawn per case (seeded).
Sensors: 8 per die on a uniform grid of each die's source layer; readings = true rise + N(0, NOISE^2).
Splits by program (the protocol's grouping unit): seeded, 12 train, 4 cal, 4 test; idle is always in train.
Estimator knowledge: R, the response of each of 10 x 10 power bins per die (uniform power over a bin).

Usage: python gates/g84/make_cases.py <out.npz>
"""
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

SEED, SEGS, NOISE, M_PER_DIE, NBIN = 84, 20, 0.1, 8, 10
G71 = os.path.join(ROOT, "gates", "g71")
CPU_BLOCK_W, TPU_BLOCK_W = 1.0719, 6.9360          # G71 seed-0 block powers (cpu_s0 - 0.4 W dark, tpu_s0 - 0.4 W dark)


def factor():
    stack = model.load(os.path.join(ROOT, "configs", "stacks", "g71_3d.yaml"))
    nx, ny = stack.grid
    with tempfile.TemporaryDirectory() as td:
        _, src = to_pact.write(stack, {d.name: np.zeros((ny, nx)) for d in stack.dies}, td)
    A = sp.load_npz(os.path.join(G71, "runs/main/3d/operator/pact.A.npz")).tocsc()
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
    """Area-weighted resample of a square map M to (n, n), keeping its total."""
    k = M.shape[0]
    e = np.kron(M, np.ones((n, n))) / (n * n)          # (k n, k n), same total; then sum k x k blocks -> (n, n)
    return e.reshape(n, k, n, k).sum((1, 3))


def main(out):
    rng = np.random.default_rng(SEED)
    stack, dies, solve = factor()
    nx, ny = stack.grid
    Z = np.load(os.path.join(G71, "inputs", "maps.npz"))
    act = Z["act3"]
    (r0, c0), (r1, c1) = np.argwhere(act).min(0), np.argwhere(act).max(0) + 1
    bs = r1 - r0
    dark = np.where(act, 0.0, 0.4 / (~act).sum())

    # plumbing: G71 seed 0 through this factorisation against G71's stored PACT fields
    key = {"top": "tpu", "bot": "cpu"}
    T0 = solve([{d: Z[f"{key[d]}_s0"] for d in dies}])[0]
    F = np.load(os.path.join(G71, "runs/main/3d_fields.npz"))
    plumb = {d: float(np.abs(T0[i] - F[f"s0_{d}_pact"]).max()) for i, d in enumerate(dies)}
    print("plumbing vs G71 PACT (max |dT| K):", plumb, flush=True)

    # CPU segments from G81b
    g81b = json.load(open(os.path.join(ROOT, "gates/g81b/record/result.json")))["programs"]
    progs = sorted(p for p in g81b if p != "idle_pass1" and "dyn_W" in g81b[p])
    med = np.median([g81b[p]["dyn_W"]["mean"] for p in progs])
    tl = {p: np.loadtxt(os.path.join(ROOT, f"gates/g81b/runs/main/{p}/timeline.csv"), delimiter=",")[:, 1:] for p in progs}
    tz = np.load(os.path.join(ROOT, "gates/g72/runs/main/maps.npz"))
    tpu = {w: resample(tz[f"tpu_{w}"], bs) for w in ("W1", "W2", "W3")}   # 32 x 32 -> 20 x 20 cells, by area
    tpu_rel = {w: tpu[w].sum() / tpu["W1"].sum() for w in tpu}

    others = [p for p in progs if p != "idle"]
    order = rng.permutation(others)
    split_of = {p: "train" for p in order[:11]} | {p: "cal" for p in order[11:15]} | {p: "test" for p in order[15:19]} | {"idle": "train"}

    powers, P_bins, meta = [], [], []
    for p in progs:
        X = tl[p]
        segs = np.array_split(np.arange(len(X)), SEGS)
        mean_tog = X.sum(1).mean()
        for s in segs:
            share = X[s].sum(0).reshape(4, 4)
            share = share / share.sum() if share.sum() > 0 else np.full((4, 4), 1 / 16)   # idle asleep: no toggles, 0 W
            cpu_block = CPU_BLOCK_W * g81b[p]["dyn_W"]["mean"] / med * X[s].sum(1).mean() / mean_tog
            cpu = dark.copy(); cpu[r0:r1, c0:c1] += np.kron(share, np.ones((bs // 4, bs // 4))) / (bs // 4) ** 2 * cpu_block
            w = ("W1", "W2", "W3")[rng.integers(3)]
            t = dark.copy(); t[r0:r1, c0:c1] += tpu[w] / tpu[w].sum() * TPU_BLOCK_W * tpu_rel[w] * rng.uniform(0.9, 1.1)
            powers.append({"top": t, "bot": cpu})
            P_bins.append([M.reshape(NBIN, ny // NBIN, NBIN, nx // NBIN).sum((1, 3)).ravel() for M in (t, cpu)])
            meta.append((p, w))
    print(f"{len(powers)} cases from {len(progs)} programs; solving", flush=True)
    T = np.concatenate([solve(powers[k:k + 100]) for k in range(0, len(powers), 100)])

    # bin operator: uniform power over each 6 x 6-cell bin of each die
    basis = []
    for d in dies:
        for b in range(NBIN * NBIN):
            M = np.zeros((ny, nx)); bi, bj = divmod(b, NBIN); h = ny // NBIN
            M[bi * h:(bi + 1) * h, bj * h:(bj + 1) * h] = 1.0 / (h * h)
            basis.append({dd: (M if dd == d else np.zeros((ny, nx))) for dd in dies})
    R = np.concatenate([solve(basis[k:k + 100]) for k in range(0, len(basis), 100)])

    sens = np.concatenate([[(i, *divmod(int(s), nx)) for s in uniform_grid((ny, nx), M_PER_DIE, offset=0.5)] for i in range(len(dies))])
    readings = T[:, sens[:, 0], sens[:, 1], sens[:, 2]] + rng.normal(0, NOISE, (len(T), len(sens)))
    group = np.array([m[0] for m in meta]); split = np.array([split_of[g] for g in group])
    cs = CaseSet(dict(T=T.astype(np.float32), P=np.array(P_bins, np.float32), R=R.astype(np.float32), readings=readings,
                      sensors=sens, noise_K=NOISE, split=split, group=group, tag=np.where(split == "test", "unseen-workload", "seen-group"),
                      tpu_workload=np.array([m[1] for m in meta]), dies=np.array(dies), buried=np.array([d == "bot" for d in dies]),
                      cell_um=float(stack.size_um[0] / nx), stack_id="g71_3d"))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    cs.save(out)
    info = {"sha256": cs.sha256(), "cases": cs.N, "split": {s: int((split == s).sum()) for s in ("train", "cal", "test")},
            "programs_by_split": {s: sorted(p for p, v in split_of.items() if v == s) for s in ("train", "cal", "test")},
            "plumbing_max_dT_K": plumb, "seed": SEED, "noise_K": NOISE, "sensors_per_die": M_PER_DIE, "bins_per_die": NBIN * NBIN,
            "peak_rise_K": {d: [float(T[:, i].max((1, 2)).min()), float(T[:, i].max((1, 2)).max())] for i, d in enumerate(dies)}}
    json.dump(info, open(os.path.splitext(out)[0] + ".json", "w"), indent=1)
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
