"""Build the G71 input power maps from the exploratory G38 sources (run once on the host; the output is committed).

Same tiles, seeds and placement as experiments/code/sens/g38.py:
  - CPU die: 13 x 13 real-activity ASAP7 ibex tiles in a 1 mm block, about 1.45 W;
  - TPU die: 10 x 10 real-activity TPU tiles in a 1 mm block, about 7.3-7.9 W;
  - 0.05 W/mm^2 dark power elsewhere on each die. Cells are 50 um.
3 x 3 mm dies use G38's block position (1, 1) mm. The 2.5D layout is new: two 2 x 2 mm chiplet regions,
0.2 mm apart, on a 4.4 x 3 mm footprint, with dark power only inside the chiplet regions.

Usage: python gates/g71/make_maps.py <asap7 build dir> <out.npz>
"""
import hashlib
import os
import re
import sys

import numpy as np

CELL, DARK = 50.0, 0.05e-6                      # um; dark density W/um^2
NUM = r"[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?"


def tpu_tile(a7, w):
    L = open(os.path.join(a7, "asap7-tpu", "inst_loc.csv")).read().splitlines()
    x0, y0, x1, y1 = [float(v) for v in L[0].split(",")[1:]]
    pos = {p[0]: (float(p[1]), float(p[2])) for p in (l.split(",") for l in L[1:])}
    M = np.zeros((32, 32))
    for l in open(os.path.join(a7, f"tpw_{w}_TT.txt"), errors="replace"):
        p = l.split()
        if len(p) == 5 and all(re.fullmatch(NUM, v) for v in p[:4]) and p[4] in pos:
            x, y = pos[p[4]]
            M[min(31, int((y - y0) / (y1 - y0) * 32)), min(31, int((x - x0) / (x1 - x0) * 32))] += float(p[3])
    return M


def place(grid, tiles, x0, y0, pitch):
    """Each tile's 32 x 32 bins as point sources into the die grid (as in G38)."""
    ny, nx = grid.shape
    for (ti, tj), M in tiles.items():
        b = pitch / 32
        ys = y0 + ti * pitch + (np.arange(32) + 0.5) * b
        xs = x0 + tj * pitch + (np.arange(32) + 0.5) * b
        I = np.minimum(ny - 1, (ys / CELL).astype(int))
        J = np.minimum(nx - 1, (xs / CELL).astype(int))
        np.add.at(grid, (I[:, None].repeat(32, 1), J[None, :].repeat(32, 0)), M)


def box(x0, y0, w, h):
    return slice(int(y0 / CELL), int((y0 + h) / CELL)), slice(int(x0 / CELL), int((x0 + w) / CELL))


def masks(shape, blocks, dark_regions):
    """Active-block masks and the dark-power mask (dark regions minus the blocks)."""
    act = np.zeros(shape, bool)
    for b in blocks:
        act[box(*b, 1000, 1000)] = True
    dark = np.zeros(shape, bool)
    for r in dark_regions:
        dark[box(*r)] = True
    return act, dark & ~act


def main(a7, out):
    m34 = np.load(os.path.join(a7, "g34_maps.npz"))
    cpu_t = {p: m34[f"TT_k{k}"] for k, p in enumerate(["matmul", "crc32", "sort", "idle", "sleep"])}
    tpu_t = {w: tpu_tile(a7, w) for w in ("W1", "W2", "W3")}
    res = {}
    # 3 x 3 mm dies (60 x 60), block at (1, 1) mm
    act3, dark3 = masks((60, 60), [(1000, 1000)], [(0, 0, 3000, 3000)])
    # 2.5D: 4.4 x 3 mm (88 x 60); chiplets at x 0.1-2.1 and 2.3-4.3 mm, y 0.5-2.5 mm; CPU block at (0.6, 1), TPU at (2.8, 1)
    act25, dark25 = masks((60, 88), [(600, 1000), (2800, 1000)], [(100, 500, 2000, 2000), (2300, 500, 2000, 2000)])
    for seed in range(4):
        r = np.random.default_rng(seed)
        cpu = {(i, j): cpu_t[r.choice(list(cpu_t))] for i in range(13) for j in range(13)}
        tpu = {(i, j): tpu_t[r.choice(["W1", "W2", "W3"], p=[0.4, 0.4, 0.2])] for i in range(10) for j in range(10)}
        C = np.where(dark3, DARK * CELL * CELL, 0.0); place(C, cpu, 1000, 1000, 1000 / 13)
        T = np.where(dark3, DARK * CELL * CELL, 0.0); place(T, tpu, 1000, 1000, 100.0)
        M = np.where(dark25, DARK * CELL * CELL, 0.0); place(M, cpu, 600, 1000, 1000 / 13); place(M, tpu, 2800, 1000, 100.0)
        res.update({f"cpu_s{seed}": C, f"tpu_s{seed}": T, f"m25_s{seed}": M})
        print(f"seed {seed}: CPU {C.sum():.3f} W, TPU {T.sum():.3f} W, 2.5D {M.sum():.3f} W")
    srcs = [os.path.join(a7, f) for f in ("g34_maps.npz", "asap7-tpu/inst_loc.csv", "tpw_W1_TT.txt", "tpw_W2_TT.txt", "tpw_W3_TT.txt")]
    sha = {os.path.relpath(f, a7).replace("\\", "/"): hashlib.sha256(open(f, "rb").read()).hexdigest() for f in srcs}
    np.savez_compressed(out, act3=act3, dark3=dark3, act25=act25, dark25=dark25, sources=repr(sha), **res)


if __name__ == "__main__":
    main(*sys.argv[1:3])
