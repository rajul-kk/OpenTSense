"""Run PACT.py unchanged, but save the conductance matrix A and right-hand side b it hands to SuperLU.

PACT's SuperLU solver assembles A (one node per grid cell per layer, flattened as layer, row, col) and calls
scipy.sparse.linalg.splu once. Saving A lets the response operator reuse PACT's own model for many power
patterns with one factorisation (see thermal.response).
Usage (from $PACT_SRC): python pact_capture.py <out prefix> <PACT.py args...>
"""
import runpy
import sys

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as sla

out = sys.argv.pop(1)
_splu = sla.splu


class _Capture:
    def __init__(self, lu):
        self.lu = lu

    def solve(self, b):
        np.save(out + ".b.npy", b)
        return self.lu.solve(b)


def splu(A, *args, **kwargs):
    sp.save_npz(out + ".A.npz", sp.csc_matrix(A))
    return _Capture(_splu(A, *args, **kwargs))


sla.splu = splu
sys.argv = ["PACT.py"] + sys.argv[1:]
sys.path.insert(0, ".")
runpy.run_path("PACT.py", run_name="__main__")
