"""Linear response operator of a stack, from PACT's own conductance matrix.

The steady model is linear: rise = G^-1 P. One PACT run (with capture) gives G; it is factorised once with the
same SuperLU options PACT uses, and each basis power pattern becomes one right-hand side.
"""
import os

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as sla

from ..stack import to_pact
from .run import run_pact

# PACT's own SuperLU settings, so our solves match its steady solution
SUPERLU = dict(permc_spec="MMD_AT_PLUS_A", diag_pivot_thresh=0.001,
               options=dict(Fact="DOFACT", Equil=False, SymmetricMode=True))


def rhs(stack, power, src):
    """Right-hand side for a power pattern {die: (ny, nx) W}, in PACT's (layer, row, col) order."""
    nx, ny = stack.grid
    b = np.zeros((max(src.values()) + 1, ny, nx))
    for d, P in power.items():
        b[src[d]] = to_pact.rows(P)
    return b.ravel()


def build(stack, basis, workdir, batch=64, observe=None, dtype=np.float64):
    """basis: list of {die: (ny, nx) W}. Returns R with R[k][die] = rise map (ny, nx) for basis pattern k,
    as an array of shape (n_basis, n_dies, ny, nx) with dies in stack order.
    observe (G93a, for large multi-die stacks): {die: (ny, nx) bool mask}. Then only those cells are kept, and R has
    shape (n_basis, n_observed), cells ordered by die (in `observe` order) then row-major. dtype=np.float32 halves R."""
    nx, ny = stack.grid
    lu, src, n = _factor(stack, basis[0], workdir)
    if observe is not None:
        idx = np.concatenate([to_pact.cell(stack, src[d], *np.nonzero(m)) for d, m in observe.items()])
        R = np.zeros((len(basis), len(idx)), dtype)
        for k0, X in _solves(lu, stack, basis, src, n, batch):
            R[k0:k0 + X.shape[1]] = X[idx].T
        return R
    dies = [d.name for d in stack.dies]
    R = np.zeros((len(basis), len(dies), ny, nx), dtype)
    for k0, X in _solves(lu, stack, basis, src, n, batch):
        for i, d in enumerate(dies):
            block = X[src[d] * nx * ny:(src[d] + 1) * nx * ny].T.reshape(-1, ny, nx)
            R[k0:k0 + X.shape[1], i] = to_pact.rows(block)
    return R


def _factor(stack, power, workdir):
    """One captured PACT run on `power`: the factorised matrix, {die: PACT source layer}, and the system size.
    Checks our right-hand side layout against PACT's, which must agree on every layer but the top (ambient term)."""
    nx, ny = stack.grid
    _, src = run_pact(stack, power, workdir, capture=True, return_src=True)
    A = sp.load_npz(os.path.join(workdir, "pact.A.npz")).tocsc()
    b = np.load(os.path.join(workdir, "pact.b.npy")).ravel()
    mine = np.zeros_like(b)
    r0 = rhs(stack, power, src)
    mine[:len(r0)] = r0
    keep = slice(0, len(b) - nx * ny)
    if not np.allclose(mine[keep], b[keep], rtol=1e-9, atol=1e-15):
        raise RuntimeError("PACT right-hand side layout differs from ours")
    return sla.splu(A, **SUPERLU), src, len(b)


def _solves(lu, stack, basis, src, n, batch):
    """(first basis index, solutions of shape (n, batch)) for the basis in batches."""
    for k0 in range(0, len(basis), batch):
        B = np.zeros((n, min(batch, len(basis) - k0)))
        for j, pat in enumerate(basis[k0:k0 + batch]):
            r = rhs(stack, pat, src)
            B[:len(r), j] = r
        yield k0, lu.solve(B)


def apply(R, coeffs):
    """Superpose: sum_k coeffs[k] * R[k]."""
    return np.tensordot(coeffs, R, axes=1)
