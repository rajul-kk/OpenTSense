"""G94 dry: the slowest thermal time constants of each stack (sizes the step case; no solver comparison).

On PACT's network (A captured from one steady PACT run, C as run.pact_transient): the smallest eigenvalues lambda
of A v = lambda C v give tau = 1 / lambda.
Usage (opentsense:g94a, repo root): python gates/g94/dry/time_constants.py <out.json>
"""
import json
import os
import sys
import tempfile

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as sla

sys.path[:0] = [".", os.path.join("gates", "g94")]
import cases  # noqa: E402
from opentsense.stack import model, to_pact  # noqa: E402
from opentsense.thermal.run import run_pact  # noqa: E402


def main(out, names=None):
    res = json.load(open(out)) if os.path.exists(out) else {}
    for name, (cfg, _) in cases.STACKS.items():
        if name in res or (names and name not in names):
            continue
        stack = model.load(os.path.join("configs", "stacks", cfg))
        with tempfile.TemporaryDirectory() as wd:
            run_pact(stack, cases.maps(name, 1), wd, capture=True)      # seed 1: A does not depend on power
            A = sp.load_npz(os.path.join(wd, "pact.A.npz")).tocsc()
        C = to_pact.capacity(stack)
        s = 1 / np.sqrt(C)
        S = sp.diags(s) @ A @ sp.diags(s)                     # symmetric when A is
        asym = float(abs(S - S.T).max() / abs(S).max())
        lam = np.sort(sla.eigsh((S + S.T) / 2, k=4, sigma=0, which="LM", return_eigenvectors=False))
        res[name] = {"tau_s": [float(1 / x) for x in lam], "nodes": int(A.shape[0]), "A_asymmetry": asym}
        print(name, res[name], flush=True)
        json.dump(res, open(out, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
