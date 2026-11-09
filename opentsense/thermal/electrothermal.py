"""Gate-level leakage-temperature loop on a linear thermal operator (G92).

Each instance carries its own leakage at a few temperatures (from per-temperature Liberty files). Its leakage at
its tile's temperature is interpolated log-linearly, extending the last segment beyond the table. Tile power is
dynamic power plus the summed instance leakage, and the steady loop is T = T_amb + R @ P(T).
"""
import numpy as np


class LeakModel:
    def __init__(self, temps_C, leak_W, tile, n_tiles, scale=1.0):
        """temps_C: (m,) table temperatures; leak_W: (n_inst, m) leakage; tile: (n_inst,) tile index of each instance."""
        self.t = np.asarray(temps_C, float)
        L = np.asarray(leak_W, float) * scale
        self.pos = (L > 0).all(axis=1)          # instances with zero leakage (fillers) stay zero
        self.ln = np.log(np.where(self.pos[:, None], L, 1.0))
        self.tile, self.n = np.asarray(tile), n_tiles

    def inst(self, T_inst_C):
        t, ln = self.t, self.ln
        k = np.clip(np.searchsorted(t, T_inst_C) - 1, 0, len(t) - 2)       # segment index; ends extend outwards
        w = (T_inst_C - t[k]) / (t[k + 1] - t[k])
        rows = np.arange(len(ln))
        y = ln[rows, k] + w * (ln[rows, k + 1] - ln[rows, k])
        return np.where(self.pos, np.exp(y), 0.0)

    def tiles(self, T_tile_K):
        Tc = np.asarray(T_tile_K)[self.tile] - 273.15
        return np.bincount(self.tile, weights=self.inst(Tc), minlength=self.n)

    def at(self, T_C):
        """Leakage per tile with every instance at one fixed temperature (deg C)."""
        return np.bincount(self.tile, weights=self.inst(np.full(len(self.ln), float(T_C))), minlength=self.n)


def solve(R, dyn, leak, T_amb, tol=1e-10, max_it=500, T0=None):
    """Fixed-point iteration. Returns (T, iterations, converged, history of max change)."""
    T = np.full(len(dyn), T_amb) if T0 is None else T0.copy()
    hist = []
    for it in range(1, max_it + 1):
        Tn = T_amb + R @ (dyn + leak.tiles(T))
        d = float(np.abs(Tn - T).max())
        hist.append(d)
        T = Tn
        if not np.isfinite(d) or d > 1e4:
            return T, it, False, hist
        if d < tol:
            return T, it, True, hist
    return T, max_it, False, hist


def rho(R, leak, T, h=0.5):
    """Spectral radius of R @ diag(dP_leak/dT) at T, by central difference of each tile's own leakage."""
    D = (leak.tiles(T + h) - leak.tiles(T - h)) / (2 * h)
    return float(np.abs(np.linalg.eigvals(R * D[None, :])).max()), D


def amplification(R, dyn, leak, T_amb, T_star):
    """G74's measured ratio on the peak tile: (T* - T_u) / (T_1 - T_u), with T_u at fixed-25 C leakage."""
    Tu = T_amb + R @ (dyn + leak.at(25.0))
    T1 = T_amb + R @ (dyn + leak.tiles(Tu))
    p = int(np.argmax(T_star))
    return float((T_star[p] - Tu[p]) / (T1[p] - Tu[p])), Tu, T1, p
