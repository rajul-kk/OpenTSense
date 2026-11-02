"""G74 inputs: rebuild the exploratory power maps and leakage curves from the archive into one file.
Usage: prep.py <archive> <asap7 build> <exploratory code> <out.npz>"""
import json
import os
import re
import sys

import numpy as np

ARCH, A7, CODE, OUT = sys.argv[1:5]
NUM = r"[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?"
G = 32
DIE = 510.555                                  # um; G31's recorded area is exactly this squared


def report(path):
    for l in open(path, errors="replace"):
        p = l.split()
        if len(p) == 5 and all(re.fullmatch(NUM, v) for v in p[:4]):
            yield p[4], [float(v) for v in p[:4]]


# ---------- sky130 ibex: instance centres and masters from the placed geometry
pos, master = {}, {}
for l in open(os.path.join(ARCH, "sens/phys/base_geom.csv"), errors="replace").read().splitlines()[1:]:
    p = l.split(",")
    if p[0] == "ROW" or len(p) < 7:
        continue
    pos[p[0]] = ((float(p[2]) + float(p[4]) / 2) / 1000, (float(p[3]) + float(p[5]) / 2) / 1000)
    master[p[0]] = p[1].replace("sky130_fd_sc_hd__", "")

curves = json.load(open(os.path.join(CODE, "sens/g35/g35bf.json")))
TYPES = list(curves["curves_W"])
out = {"sky_T": np.array(curves["T"], float), "sky_types": np.array(TYPES)}
for t in TYPES:
    c = curves["curves_W"][t]
    out[f"sky_lnF_{t}"] = np.log(np.array([c[str(x) if str(x) in c else repr(x)] for x in curves["T"]]) / c["25"])


def cell(n):
    x, y = pos[n]
    return min(G - 1, int(y / DIE * G)), min(G - 1, int(x / DIE * G))


for k in range(4):
    dyn = np.zeros((G, G)); L = np.zeros((len(TYPES) + 1, G, G)); L100 = np.zeros((G, G)); matched = 0
    for n, v in report(os.path.join(ARCH, f"etsim/build/p_k{k}_025C.txt")):
        if n in pos:                           # the 2 hierarchical rollups are not placed, so they drop out here
            i, j = cell(n); matched += 1
            dyn[i, j] += v[0] + v[1]
            L[TYPES.index(master[n]) if master[n] in TYPES else -1, i, j] += v[2]
    for n, v in report(os.path.join(ARCH, f"etsim/build/p_k{k}_100C.txt")):
        if n in pos:
            L100[cell(n)] += v[2]
    out[f"sky_dyn_k{k}"], out[f"sky_L_k{k}"], out[f"sky_L100_k{k}"] = dyn, L, L100
    print("sky130", k, "instances", matched, "total W", dyn.sum() + L.sum(), flush=True)

# ---------- ASAP7: G38 die maps, binned as G41 did, on the G39 operator
NG, CELL, DARK, TILE = 60, 3000.0 / 60, 0.05e-6, 1000.0
M34 = np.load(os.path.join(A7, "g34_maps.npz"))
CPU = {p: M34[f"TT_k{k}"] for k, p in enumerate(["matmul", "crc32", "sort", "idle", "sleep"])}


def tpu_map(w):
    L = open(os.path.join(A7, "asap7-tpu/inst_loc.csv")).read().splitlines()
    x0, y0, x1, y1 = [float(v) for v in L[0].split(",")[1:]]
    loc = {p[0]: (float(p[1]), float(p[2])) for p in (l.split(",") for l in L[1:])}
    M = np.zeros((32, 32))
    for n, v in report(os.path.join(A7, f"tpw_{w}_TT.txt")):
        if n in loc:
            x, y = loc[n]
            M[min(31, int((y - y0) / (y1 - y0) * 32)), min(31, int((x - x0) / (x1 - x0) * 32))] += v[3]
    return M


TPU = {w: tpu_map(w) for w in ("W1", "W2", "W3")}


def place(grid, tiles, x0, y0, pitch):
    for (ti, tj), M in tiles.items():
        b = pitch / 32
        ys = y0 + ti * pitch + (np.arange(32) + 0.5) * b
        xs = x0 + tj * pitch + (np.arange(32) + 0.5) * b
        I = np.minimum(NG - 1, (ys / CELL).astype(int)); J = np.minimum(NG - 1, (xs / CELL).astype(int))
        np.add.at(grid, (I[:, None].repeat(32, 1), J[None, :].repeat(32, 0)), M)


def die_maps(seed):
    r = np.random.default_rng(seed)
    dark = np.full((NG, NG), DARK * CELL * CELL)
    cpu = {(i, j): CPU[r.choice(list(CPU))] for i in range(13) for j in range(13)}
    tpu = {(i, j): TPU[r.choice(["W1", "W2", "W3"], p=[0.4, 0.4, 0.2])] for i in range(10) for j in range(10)}
    blk = (slice(int(TILE / CELL), int(2 * TILE / CELL)),) * 2
    C = dark.copy(); C[blk] = 0; place(C, cpu, TILE, TILE, TILE / 13)
    T = dark.copy(); T[blk] = 0; place(T, tpu, TILE, TILE, 100.0)
    return C, T


def binp(M):
    b = [M[20 + 2 * i:22 + 2 * i, 20 + 2 * j:22 + 2 * j].sum() for i in range(10) for j in range(10)]
    m = np.ones((60, 60), bool); m[20:40, 20:40] = False
    return np.array(b + [M[m].sum()])


for s in range(4):
    C, T = die_maps(s)
    out[f"a7_pt_{s}"], out[f"a7_pc_{s}"] = binp(T), binp(C)
    print("asap7 stack", s, "TPU W", T.sum(), "CPU W", C.sum(), flush=True)
out["a7_A"] = np.stack([np.load(os.path.join(ARCH, f"sens/g39/op/c{j:03d}.npy")) for j in range(202)], 1)

g41 = json.load(open(os.path.join(CODE, "sens/g41/g41_res.json")))
ROWS = 4                                       # 25, 50, 75, 100 C; the 125 C row holds failed solves (Amendment 1)
R = {k: np.array(v[:ROWS]) for k, v in g41["spice_leak_W"].items()}
for vt in ("R", "L", "SL"):
    out[f"a7_curve_{vt}"] = np.exp(np.mean([np.log(R[f"{c}_{vt}"] / R[f"{c}_{vt}"][0]) for c in ("INVx1", "NAND2x1", "DFFHQNx1")], 0))
mix = {"R": 28928, "L": 8096, "SL": 19322}     # TPU cell counts per threshold flavour, as in G41
lw = {vt: mix[vt] * R[f"INVx1_{vt}"][0] for vt in mix}
out["a7_curve_tpu"] = sum(lw[v] * out[f"a7_curve_{v}"] for v in mix) / sum(lw.values())
out["a7_T"] = np.array([25.0, 50.0, 75.0, 100.0])

os.makedirs(os.path.dirname(OUT), exist_ok=True)
np.savez_compressed(OUT, **out)
print("wrote", OUT, os.path.getsize(OUT) / 1e6, "MB")
