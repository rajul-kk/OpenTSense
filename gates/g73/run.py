"""G73: do prior-aware identifiability numbers predict per-die power error in a two-die stack?
Usage: run.py <archive sens dir> <asap7 build> <exploratory code> <run dir> [--plumbing]"""
import json
import os
import re
import sys

import numpy as np
import scipy.linalg as sl
from scipy.stats import spearmanr

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from opentsense import manifest  # noqa: E402

ARCH, A7, CODE, RUN = sys.argv[1:5]
PLUMBING = "--plumbing" in sys.argv
os.makedirs(RUN, exist_ok=True)
NUM = r"[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?"
NG, CELL, DARK, B0, NB, n2 = 60, 50.0, 0.05e-6, 20, 10, 3600
SIG = 0.65
BONDS = {"B0_microbump": "g39/op", "B1_hybrid": "g54/B1_hybrid/op", "B2_m3dlike": "g54/B2_m3dlike/op"}
TOPC, BOTC = np.arange(101), np.arange(101, 202)
TOPB, BOTB = np.arange(100), np.arange(101, 201)
blockmask = np.zeros((NG, NG), bool); blockmask[B0:B0 + 20, B0:B0 + 20] = True
cand = np.flatnonzero(blockmask.ravel())

# ---------- G42 generator -----------------------------------------------------------------------
M34 = np.load(os.path.join(A7, "g34_maps.npz"))
CPU = {p: M34[f"TT_k{k}"] for k, p in enumerate(["matmul", "crc32", "sort", "idle", "sleep"])}


def tpu_map(w):
    L = open(os.path.join(A7, "asap7-tpu/inst_loc.csv")).read().splitlines()
    x0, y0, x1, y1 = [float(v) for v in L[0].split(",")[1:]]
    loc = {p[0]: (float(p[1]), float(p[2])) for p in (l.split(",") for l in L[1:])}
    M = np.zeros((32, 32))
    for l in open(os.path.join(A7, f"tpw_{w}_TT.txt"), errors="replace"):
        p = l.split()
        if len(p) == 5 and all(re.fullmatch(NUM, v) for v in p[:4]) and p[4] in loc:
            x, y = loc[p[4]]
            M[min(31, int((y - y0) / (y1 - y0) * 32)), min(31, int((x - x0) / (x1 - x0) * 32))] += float(p[3])
    return M


TPU = {w: tpu_map(w) for w in ("W1", "W2", "W3")}


def place(grid, tiles, x0, y0, pitch):
    for (ti, tj), M in tiles.items():
        b = pitch / 32
        ys = y0 + ti * pitch + (np.arange(32) + 0.5) * b
        xs = x0 + tj * pitch + (np.arange(32) + 0.5) * b
        I = np.minimum(NG - 1, (ys / CELL).astype(int)); J = np.minimum(NG - 1, (xs / CELL).astype(int))
        np.add.at(grid, (I[:, None].repeat(32, 1), J[None, :].repeat(32, 0)), M)


def phase_power(seed):
    r = np.random.default_rng(seed); dark = np.full((NG, NG), DARK * CELL * CELL); comp = ["matmul", "crc32", "sort", "idle"]
    ph_c = r.choice(["busy", "cluster", "half", "sleep"]); ph_t = r.choice(["dense", "mixed", "partial", "idle"])
    on = np.zeros((13, 13), bool)
    if ph_c == "busy":
        on[:] = True
    elif ph_c == "cluster":
        h, w = r.integers(3, 10, 2); a, b = r.integers(0, 13 - h + 1), r.integers(0, 13 - w + 1); on[a:a + h, b:b + w] = True
    elif ph_c == "half":
        on = r.random((13, 13)) < 0.5
    cpu = {(i, j): (CPU[r.choice(comp)] if on[i, j] else CPU["sleep"]) for i in range(13) for j in range(13)}
    tp = np.full((10, 10), "W3", dtype=object)
    if ph_t == "dense":
        tp[:] = "W1"
    elif ph_t == "mixed":
        tp = np.where(r.random((10, 10)) < 0.5, "W1", "W2")
    elif ph_t == "partial":
        h, w = r.integers(2, 9, 2); a, b = r.integers(0, 10 - h + 1), r.integers(0, 10 - w + 1); tp[a:a + h, b:b + w] = "W1"
    tpu = {(i, j): TPU[tp[i, j]] for i in range(10) for j in range(10)}
    blk = (slice(20, 40), slice(20, 40))
    C = dark.copy(); C[blk] = 0; place(C, cpu, 1000, 1000, 1000 / 13)
    T = dark.copy(); T[blk] = 0; place(T, tpu, 1000, 1000, 100.0)
    p = []
    for M in (T, C):
        p += [M[B0 + 2 * bi:B0 + 2 * bi + 2, B0 + 2 * bj:B0 + 2 * bj + 2].sum() for bi in range(NB) for bj in range(NB)]
        p.append(M[~blockmask].sum())
    return np.array(p)


# ---------- estimator -------------------------------------------------------------------------------
def prior(P):
    mu = P.mean(0); C = np.cov(P.T)
    return mu, C + 1e-3 * np.trace(C) / len(C) * np.eye(len(C))


def dopt(S, idx, K, sig):
    Sg = S[np.ix_(idx, idx)].copy(); sel = []
    for _ in range(K):
        v = np.diag(Sg).copy(); v[sel] = -np.inf; j = int(np.argmax(v)); sel.append(j)
        c = Sg[:, j].copy(); Sg -= np.outer(c, c) / (Sg[j, j] + sig ** 2)
    return [int(idx[s]) for s in sel]


def sensors(A, C, K):
    S = A @ C @ A.T
    return dopt(S, cand, K // 2, SIG) + dopt(S, cand + n2, K // 2, SIG)


def bayes(H, mu, C, Y, s2):
    Kg = C @ H.T @ np.linalg.inv(H @ C @ H.T + s2 * np.eye(len(H)))
    return mu + (Y - mu @ H.T) @ Kg.T, Kg


def rel(a, b):
    return float(np.mean(np.linalg.norm(a - b, axis=1) / np.linalg.norm(b, axis=1)))


def dfs(H, C, cols):
    Kg = C @ H.T @ np.linalg.inv(H @ C @ H.T + SIG ** 2 * np.eye(len(H)))
    return float(np.trace((Kg @ H)[np.ix_(cols, cols)]))


def whitened(H, C, d, o):
    Hd, Ho = H[:, d], H[:, o]
    N = SIG ** 2 * np.eye(len(H)) + Ho @ C[np.ix_(o, o)] @ Ho.T
    W = np.linalg.inv(np.linalg.cholesky(N))
    Cs = np.real(sl.sqrtm(C[np.ix_(d, d)]))
    return W, W @ Hd @ Cs


OP = {b: np.stack([np.load(os.path.join(ARCH, p, f"c{j:03d}.npy")) for j in range(202)], 1) for b, p in BONDS.items()}
Ptrain = np.array([phase_power(s) for s in range(300, 420)])
Pcal = np.array([phase_power(s) for s in range(420, 440)])
Pg42te = np.array([phase_power(s) for s in range(440, 500)])

# ---------- plumbing --------------------------------------------------------------------------------
gen_err = 0.0
for s in range(300, 500):
    gen_err = max(gen_err, 0.0)
stored = [os.path.join(ARCH, "g39/tr", f"p{s}.npz") for s in range(300, 500)]
have_p = all(os.path.exists(f) for f in stored)
if have_p:
    Pst = np.array([np.load(f)["p"] for f in stored])
    gen_err = float(np.abs(np.r_[Ptrain, Pcal, Pg42te] - Pst).max())
g54 = json.load(open(os.path.join(CODE, "sens/g54/g54_res.json")))["results"]
rng = np.random.default_rng(54); pl = {}
for b, A in OP.items():
    trd = "g39/tr" if b == "B0_microbump" else f"g54/{b}/tr"
    files = [os.path.join(ARCH, trd, f"p{s}.npz") for s in range(300, 500)]
    if not all(os.path.exists(f) for f in files):
        pl[b] = dict(missing_truth=True); continue
    Tt = np.array([np.load(f)["T"] for f in files])
    mu, C = prior(Ptrain); sel = sensors(A, C, 16); H = A[sel]
    Yc = np.repeat(Tt[120:140][:, sel], 10, 0) + rng.normal(0, SIG, (200, 16)); Tc = np.repeat(Tt[120:140], 10, 0)
    errs = {}
    for inf in (1, 2, 4, 8, 16):
        Th = bayes(H, mu, C, Yc, inf * SIG ** 2)[0] @ A.T
        errs[inf] = np.abs(Th[:, n2:].max(1) - Tc[:, n2:].max(1)).mean()
    inf = min(errs, key=errs.get)
    Yt = np.repeat(Tt[140:200][:, sel], 10, 0) + rng.normal(0, SIG, (600, 16)); Pt = np.repeat(Pg42te, 10, 0)
    Ph = bayes(H, mu, C, Yt, inf * SIG ** 2)[0]
    e = dict(cpu=rel(Ph[:, BOTB], Pt[:, BOTB]), tpu=rel(Ph[:, TOPB], Pt[:, TOPB]), rec_cpu=g54[b]["sigma0.65"]["pow_rel_cpu"], rec_tpu=g54[b]["sigma0.65"]["pow_rel_tpu"], infl=inf)
    pl[b] = e
plumb = dict(generator_stored=have_p, generator_max_err_W=gen_err, g54=pl)
worst = [max(abs(e["cpu"] - e["rec_cpu"]), abs(e["tpu"] - e["rec_tpu"])) for e in pl.values() if "cpu" in e]
plumb["g54_worst"] = max(worst) if worst else None
plumb["ok"] = bool(have_p and gen_err <= 1e-9 and len(worst) == 3 and max(worst) <= 0.03)
print("plumbing", json.dumps(plumb), flush=True)
if PLUMBING or not plumb["ok"]:
    json.dump(plumb, open(os.path.join(RUN, "plumbing.json"), "w"), indent=1)
    sys.exit(0 if PLUMBING else 1)

# ---------- gate ------------------------------------------------------------------------------------
Ptest = np.array([phase_power(s) for s in range(500, 660)])
rng = np.random.default_rng(73); mu, C = prior(Ptrain)
scale = np.ones(202); scale[BOTC] = np.sqrt(np.trace(C[np.ix_(TOPC, TOPC)]) / np.trace(C[np.ix_(BOTC, BOTC)]))
Ceq = C * np.outer(scale, scale)               # equal-power control: both dies carry the same prior trace
rows, pic = [], {}
for b, A in OP.items():
    for K in (8, 16, 32):
        sel = sensors(A, C, K); H = A[sel]
        Y = np.repeat(Ptest @ H.T, 10, 0) + rng.normal(0, SIG, (1600, K)); Pt = np.repeat(Ptest, 10, 0)
        Ph = bayes(H, mu, C, Y, SIG ** 2)[0]
        for die, cols, blk, oth in (("top", TOPC, TOPB, BOTC), ("buried", BOTC, BOTB, TOPC)):
            W, Mw = whitened(H, C, cols, oth)
            U, sv, _ = np.linalg.svd(Mw, full_matrices=False)
            coef = np.abs(U.T @ (W @ (Y - mu @ H.T).T)).mean(1)
            rows.append(dict(bond=b, K=K, die=die, sensors=K // 2, dfs=dfs(H, C, cols), dfs_100=dfs(H, C, blk), sv_min=float(sv.min()), sv_max=float(sv.max()),
                             err=rel(Ph[:, blk], Pt[:, blk]), dfs_equal_power=dfs(H, Ceq, cols)))
            pic[f"{b}_K{K}_{die}_sv"], pic[f"{b}_K{K}_{die}_coef"] = sv, coef
        print(b, K, [(r["die"], round(r["dfs"], 2), round(r["sv_min"], 2), round(r["err"], 3), round(r["dfs_equal_power"], 2)) for r in rows[-2:]], flush=True)
d = [r["dfs"] for r in rows]; e = [r["err"] for r in rows]
rho_s = float(spearmanr(d, e)[0])
pairs = {(r["bond"], r["K"]): {} for r in rows}
for r in rows:
    pairs[(r["bond"], r["K"])][r["die"]] = r
bar_a = rho_s <= -0.8
bar_b = all(p["buried"]["dfs"] < p["top"]["dfs"] for p in pairs.values())
control = sum(p["buried"]["dfs_equal_power"] < p["top"]["dfs_equal_power"] for p in pairs.values())
within = {x: float(spearmanr([r["dfs"] for r in rows if r["die"] == x], [r["err"] for r in rows if r["die"] == x])[0]) for x in ("top", "buried")}
rho_sv = float(spearmanr([r["sv_min"] for r in rows], e)[0])
res = dict(gate="G73", verdict="PASS" if bar_a and bar_b else "FAIL", spearman_dfs_err=rho_s, bar_a=bool(bar_a), bar_b=bool(bar_b), buried_fewer_dfs=sum(p["buried"]["dfs"] < p["top"]["dfs"] for p in pairs.values()),
           equal_power_control_buried_fewer=int(control), spearman_within_die=within, spearman_svmin_err=rho_sv, rows=rows, plumbing=plumb, posterior_note="dfs per die includes the dark bin; dfs_100 excludes it")
np.savez_compressed(os.path.join(RUN, "picard.npz"), **pic)
json.dump(res, open(os.path.join(RUN, "result.json"), "w"), indent=1, default=float)
manifest.write(os.path.join(RUN, "manifest.json"))
print(json.dumps({k: res[k] for k in ("verdict", "spearman_dfs_err", "bar_a", "bar_b", "buried_fewer_dfs", "equal_power_control_buried_fewer", "spearman_within_die", "spearman_svmin_err")}, indent=1))
