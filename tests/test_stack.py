import os

import numpy as np

from opentsense.stack import model, to_3dice, to_pact

CFG = os.path.join(os.path.dirname(__file__), "..", "configs", "stacks", "single_die.yaml")


def test_load():
    s = model.load(CFG)
    assert [d.name for d in s.dies] == ["die0"]


def test_writers(tmp_path):
    s = model.load(CFG)
    P = np.full(s.grid[::-1], 1e-3)
    stk = open(to_3dice.write(s, {"die0": P}, tmp_path / "ice")).read()
    assert "die S_die0 D_die0" in stk and "S_spreader" in stk
    (lcf, _, _), src = to_pact.write(s, {"die0": P}, tmp_path / "pact")
    rows = open(lcf).read().splitlines()[1:]
    assert len(rows) == len(s.layers) + 1          # each die is split into source + bulk
    assert src == {"die0": 0}                       # bottom-up: the die's source is PACT layer 0
