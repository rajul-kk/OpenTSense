"""Linear response operator of a stack, from PACT's own conductance matrix.

The steady model is linear: rise = G^-1 P. One PACT run (with capture) gives G; it is factorised once with the
same SuperLU options PACT uses, and each basis power pattern becomes one right-hand side.
"""
import os

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as sla

from .run import run_pact


def rhs(stack, power, src):
    """Right-hand side for a power pattern {die: (ny, nx) W}, in PACT's (layer, row, col) order."""
    nx, ny = stack.grid
    n_layers = max(src.values()) + 1
    b = np.zeros((n_layers, ny, nx))
    for d, P in power.items():
        b[src[d]] = P[::-1]                        # PACT row r is our row ny-1-r
    return b.ravel()


def build(stack, basis, workdir, batch=64, observe=None, dtype=np.float64):
    """basis: list of {die: (ny, nx) W}. Returns R with R[k][die] = rise map (ny, nx) for basis pattern k,
    as an array of shape (n_basis, n_dies, ny, nx) with dies in stack order.
    observe (G93a, for large multi-die stacks): {die: (ny, nx) bool mask}. Then only those cells are kept, and R has
    shape (n_basis, n_observed), cells ordered by die (in `observe` order) then row-major. dtype=np.float32 halves R."""
    if observe is not None:
        return _build_observed(stack, basis, workdir, batch, observe, dtype)
    nx, ny = stack.grid
    maps, src = run_pact(stack, basis[0], workdir, capture=True, return_src=True)
    A = sp.load_npz(os.path.join(workdir, "pact.A.npz")).tocsc()
    b = np.load(os.path.join(workdir, "pact.b.npy")).ravel()
    # check our right-hand side layout against PACT's: equal on every layer except the top one (ambient term)
    mine = np.zeros_like(b); r0 = rhs(stack, basis[0], src); mine[:len(r0)] = r0
    top = slice(len(b) - nx * ny, len(b))
    keep = np.ones(len(b), bool); keep[top] = False
    assert np.allclose(mine[keep], b[keep], rtol=1e-9, atol=1e-15), "PACT right-hand side layout differs from ours"
    lu = sla.splu(A, permc_spec="MMD_AT_PLUS_A", diag_pivot_thresh=0.001, options=dict(Fact="DOFACT", Equil=False, SymmetricMode=True))
    dies = [d.name for d in stack.dies]
    R = np.zeros((len(basis), len(dies), ny, nx))
    for k0 in range(0, len(basis), batch):
        B = np.zeros((len(b), min(batch, len(basis) - k0)))
        for j, pat in enumerate(basis[k0:k0 + batch]):
            r = rhs(stack, pat, src); B[:len(r), j] = r
        X = lu.solve(B)
        for j in range(B.shape[1]):
            for i, d in enumerate(dies):
                li = src[d]
                R[k0 + j, i] = X[li * nx * ny:(li + 1) * nx * ny, j].reshape(ny, nx)[::-1]
    return R


def _factor(stack, basis, workdir):
    nx, ny = stack.grid
    _, src = run_pact(stack, basis[0], workdir, capture=True, return_src=True)
    A = sp.load_npz(os.path.join(workdir, "pact.A.npz")).tocsc()
    b = np.load(os.path.join(workdir, "pact.b.npy")).ravel()
    mine = np.zeros_like(b); r0 = rhs(stack, basis[0], src); mine[:len(r0)] = r0
    keep = np.ones(len(b), bool); keep[len(b) - nx * ny:] = False
    assert np.allclose(mine[keep], b[keep], rtol=1e-9, atol=1e-15), "PACT right-hand side layout differs from ours"
    lu = sla.splu(A, permc_spec="MMD_AT_PLUS_A", diag_pivot_thresh=0.001, options=dict(Fact="DOFACT", Equil=False, SymmetricMode=True))
    return lu, src, len(b)


def _build_observed(stack, basis, workdir, batch, observe, dtype):
    nx, ny = stack.grid
    lu, src, n = _factor(stack, basis, workdir)
    # PACT index of each observed cell: layer block, then PACT row ny-1-i
    idx = np.concatenate([src[d] * nx * ny + ((ny - 1 - np.nonzero(m)[0]) * nx + np.nonzero(m)[1]) for d, m in observe.items()])
    R = np.zeros((len(basis), len(idx)), dtype)
    for k0 in range(0, len(basis), batch):
        B = np.zeros((n, min(batch, len(basis) - k0)))
        for j, pat in enumerate(basis[k0:k0 + batch]):
            r = rhs(stack, pat, src); B[:len(r), j] = r
        R[k0:k0 + B.shape[1]] = lu.solve(B)[idx].T
    return R


def apply(R, coeffs):
    """Superpose: sum_k coeffs[k] * R[k]."""
    return np.tensordot(coeffs, R, axes=1)
