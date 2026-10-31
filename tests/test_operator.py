import os

import numpy as np
import pytest

from opentsense.stack import model
from opentsense.thermal import response
from opentsense.thermal.run import PACT_SRC, run_pact

CFG = os.path.join(os.path.dirname(__file__), "..", "configs", "stacks", "single_die.yaml")


@pytest.mark.skipif(not os.path.isdir(PACT_SRC), reason="needs PACT (run inside the image)")
def test_operator_matches_full_solve(tmp_path):
    s = model.load(CFG)
    s.layers[0].n_sub = 3
    nx, ny = s.grid
    basis = []
    for i in range(ny):
        for j in range(nx):
            P = np.zeros((ny, nx)); P[i, j] = 1.0; basis.append({"die0": P})
    R = response.build(s, basis, str(tmp_path / "op"))
    P = np.random.default_rng(1).random((ny, nx)) * 1e-3
    T_op = response.apply(R, P.ravel())[0]
    T = run_pact(s, {"die0": P}, str(tmp_path / "full"))["die0"] - s.ambient_K
    assert np.abs(T_op - T).max() <= 0.005 + 1e-9    # PACT writes temperatures rounded to 0.01 K
