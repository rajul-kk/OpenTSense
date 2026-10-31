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


def test_sublayers_and_source_side(tmp_path):
    s = model.load(CFG)
    s.layers[0].n_sub = 4                            # spreader
    s.layers[2].n_sub = 3                            # die0 bulk
    s.layers[2].source_side = "top"
    P = np.full(s.grid[::-1], 1e-3)
    stk = open(to_3dice.write(s, {"die0": P}, tmp_path / "ice")).read()
    assert stk.count("layer S_spreader_") == 4
    die = stk.split("die D_die0 :")[1].split("stack:")[0].split(";")
    assert "source" in die[0] and all("layer" in d for d in die[1:4])   # top source first, then 3 bulk layers
    (lcf, _, _), src = to_pact.write(s, {"die0": P}, tmp_path / "pact")
    rows = open(lcf).read().splitlines()[1:]
    assert len(rows) == 4 + 1 + 4                    # 4 spreader + 1 tim + (3 bulk + 1 source)
    assert src == {"die0": 3}                        # bottom-up: 3 bulk layers, then the source
