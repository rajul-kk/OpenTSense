"""Parametric power map for a DRAM die in an HBM-style stack (G93a). Not derived from a DRAM design: there is no open
HBM layout or power model to run, so this is a stated assumption, not a measurement.

Layout (die-local, rows = y from the die's lower edge): a central horizontal TSV/IO strip, with banks on either side
in a regular grid of `banks` = (rows, columns), separated by `gap` cells of periphery.
Power = background (refresh, leakage, periphery; spread uniformly over the die)
      + activation/read/write power, split over the banks by an access mix
      + TSV/IO strip power (data movement through the stack).
Totals are inputs. For scale, Thermo's datasets cap memory dies at 2-8 W/cm^2 and cite typical HBM3 die power density
of about 0.1-0.5 W/cm^2 (Thermo docs/assumptions.md); a registration must fix the values it uses.
"""
import numpy as np


def layout(shape, banks=(2, 4), gap=1, strip_frac=0.15):
    """Integer label map: -1 periphery, -2 TSV/IO strip, k >= 0 bank k. shape = (ny, nx) cells."""
    ny, nx = shape
    lab = np.full(shape, -1)
    s = max(1, int(round(strip_frac * ny)))
    s0 = (ny - s) // 2
    lab[s0:s0 + s, :] = -2
    br, bc = banks
    halves = [(0, s0), (s0 + s, ny)]
    k = 0
    for a, b in halves:
        rows = np.array_split(np.arange(a, b), br)
        for rr in rows:
            for cc in np.array_split(np.arange(nx), bc):
                r0, r1 = rr[0] + (gap if rr[0] > a else 0), rr[-1] + 1 - gap
                c0, c1 = cc[0] + (gap if cc[0] > 0 else 0), cc[-1] + 1 - gap
                if r1 > r0 and c1 > c0:
                    lab[r0:r1, c0:c1] = k
                k += 1
    return lab


def die_map(shape, background_W, active_W, io_W, banks=(2, 4), gap=1, strip_frac=0.15, mix=None, seed=None):
    """(ny, nx) power map in W. mix: per-bank share of active_W (sums to 1); default: Dirichlet(2) draw from `seed`,
    i.e. uneven but not single-bank traffic."""
    lab = layout(shape, banks, gap, strip_frac)
    nb = lab.max() + 1
    if mix is None:
        mix = np.random.default_rng(seed).dirichlet(np.full(nb, 2.0))
    mix = np.asarray(mix, float)
    assert len(mix) == nb and np.isclose(mix.sum(), 1.0), "mix must have one share per bank and sum to 1"
    P = np.full(shape, background_W / lab.size)
    for k in range(nb):
        m = lab == k
        P[m] += active_W * mix[k] / m.sum()
    io = lab == -2
    P[io] += io_W / io.sum()
    return P
