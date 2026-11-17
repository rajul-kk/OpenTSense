"""G94 dry check (not scored): which transient is right early on? Uniform power makes the small test stack 1-D, so a
fine 1-D reference (every sublayer split 20 times, Crank-Nicolson, dt = 1 us) is the truth to compare against.
Usage (inside opentsense:g93a, repo root): python gates/g94/dry/one_d.py
"""
import sys
import tempfile

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as sla

sys.path.insert(0, ".")
from opentsense.thermal.run import run_3dice, run_hotspot, run_pact  # noqa: E402
from tests.test_solvers import small  # noqa: E402

P_TOT, SPLIT, DT, ROWS = 0.5, 20, 1e-6, [0, 1, 3, 11]


def reference(s, die, n_ms):
    """Mean source-layer rise at the end of each ms; nodes from the face away from the sink to the sink face."""
    area = s.size_um[0] * s.size_um[1] * 1e-12
    dz, k, cv, src = [], [], [], []
    for l, kind, th in s.sublayers():
        m = s.materials[l.material]
        for _ in range(SPLIT):
            dz.append(th * 1e-6 / SPLIT); k.append(m.k); cv.append(m.cv); src.append(l.name == die and kind == "src")
    dz, k, cv, src = map(np.array, (dz, k, cv, src))
    G = area / (dz[:-1] / 2 / k[:-1] + dz[1:] / 2 / k[1:])
    g_sink = area / (dz[-1] / 2 / k[-1] + 1 / s.htc)
    L = sp.diags([np.r_[G, 0] + np.r_[0, G] + np.r_[np.zeros(len(G)), g_sink], -G, -G], [0, 1, -1]).tocsc()
    C, q = cv * dz * area, np.where(src, P_TOT * dz / dz[src].sum(), 0)
    lhs, rhs = sla.splu((sp.diags(C / DT) + L / 2).tocsc()), (sp.diags(C / DT) - L / 2).tocsc()
    T, out = np.zeros(len(dz)), []
    for i in range(1, n_ms * round(1e-3 / DT) + 1):
        T = lhs.solve(rhs @ T + q)
        if i % round(1e-3 / DT) == 0:
            out.append(T[src].mean())
    return np.array(out), sla.spsolve(L, q)[src].mean()


def main():
    s = small(regions=False)
    nx, ny = s.grid
    die = s.dies[0].name
    ref, steady = reference(s, die, 12)
    P = {die: np.repeat(np.full((ny, nx), P_TOT / (nx * ny))[None], 12, 0)}
    print("mean rise of the source layer (K) at 1, 2, 4, 12 ms")
    print(f"{'1-D reference':24s}" + " ".join(f"{v:6.3f}" for v in ref[ROWS]) + f"   (steady {steady:.3f})")
    runs = [("3D-ICE, step 0.1 ms", run_3dice, 1e-4), ("HotSpot", run_hotspot, 1e-4)] + \
           [(f"PACT, step {st * 1e3:g} ms", run_pact, st) for st in (1e-4, 1e-5, 1e-6)]
    for name, f, st in runs:
        v = f(s, P, tempfile.mkdtemp(), transient=(st, 1e-3))[die].mean((1, 2)) - s.ambient_K
        print(f"{name:24s}" + " ".join(f"{x:6.3f}" for x in v[ROWS]))


if __name__ == "__main__":
    main()
