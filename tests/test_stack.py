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


# ---- G93a: lateral regions, sink side, HotSpot writer, DRAM map ----
import pytest

from opentsense.power import dram
from opentsense.stack import to_hotspot


def hetero(side="top"):
    s = model.load(CFG)
    s.materials["mould"] = model.Material(0.8, 1.8e6)
    s.sink_side = side
    d = s.dies[0]
    cx, cy = s.cell_um
    d.material = "mould"
    d.regions = [model.Region("silicon", (2 * cx, 3 * cy, 4 * cx, 5 * cy))]
    return s.validate()


def test_regions_map_and_place():
    s = hetero()
    M = s.material_map(s.dies[0])
    assert (M == "silicon").sum() == 20 and M[3, 2] == "silicon" and M[2, 2] == "mould"
    cx, cy = s.cell_um
    P = s.place(np.ones((5, 4)), (2 * cx, 3 * cy, 4 * cx, 5 * cy))
    assert P.sum() == 20 and P[3:8, 2:6].all()


def test_region_checks():
    s = model.load(CFG)
    cx, cy = s.cell_um
    with pytest.raises(ValueError):
        s.cells((0.5 * cx, 0, cx, cy))                         # off the cell grid
    s.dies[0].regions = [model.Region("silicon", (0, 0, 2 * cx, 2 * cy)), model.Region("silicon", (cx, cx, 2 * cx, 2 * cy))]
    with pytest.raises(AssertionError):
        s.validate()                                           # overlap


def test_writers_with_regions(tmp_path):
    s = hetero()
    P = {"die0": np.full(s.grid[::-1], 1e-3)}
    stk = open(to_3dice.write(s, P, tmp_path / "ice")).read()
    assert 'layout "die0.lyt"' in stk and "source LS_die0 ;" in stk and "layer LB_die0 ;" in stk
    lyt = open(tmp_path / "ice" / "die0.lyt").read()
    assert lyt.startswith("silicon :") and lyt.count("rectangle") == 1
    (lcf, cfg, _), src = to_pact.write(s, P, tmp_path / "pact")
    flp = open(tmp_path / "pact" / f"L{src['die0']}_flp.csv").read()
    lab = to_pact.label_map(s)
    assert flp.count("," + lab["silicon"] + "\n") == 20 and flp.count("," + lab["mould"] + "\n") == s.grid[0] * s.grid[1] - 20
    paths, hsrc = to_hotspot.write(s, P, tmp_path / "hs")
    lines = [l for l in open(tmp_path / "hs" / f"L{hsrc['die0']}.flp") if not l.startswith("#")]
    assert len(lines) == s.grid[0] * s.grid[1]
    assert sum(1 for l in lines if abs(float(l.split()[6]) - 1 / 130) < 1e-9) == 20     # silicon resistivity on 20 units


def test_bottom_sink_order(tmp_path):
    top, bot = hetero("top"), hetero("bottom")
    P = {"die0": np.full(top.grid[::-1], 1e-3)}
    _, s_top = to_pact.write(top, P, tmp_path / "t")
    _, s_bot = to_pact.write(bot, P, tmp_path / "b")
    n = len(open(tmp_path / "t" / "stack_lcf.csv").read().splitlines()) - 1
    assert s_top == {"die0": 0} and s_bot == {"die0": n - 1}   # source next to the far side, then next to the sink
    assert "bottom heat sink" in open(to_3dice.write(bot, P, tmp_path / "bi")).read()
    _, h_top = to_hotspot.write(top, P, tmp_path / "ht")
    _, h_bot = to_hotspot.write(bot, P, tmp_path / "hb")
    assert h_top == s_top and h_bot == s_bot


def test_hotspot_package_equivalence(tmp_path):
    s = model.load(CFG)
    paths, _ = to_hotspot.write(s, {"die0": np.full(s.grid[::-1], 1e-3)}, tmp_path)
    cfg = dict(l.split() for l in open(paths["config"]))
    side = float(cfg["-s_sink"])
    assert abs(side / (1.001 * max(s.size_um) * 1e-6) - 1) < 1e-8
    assert abs((2 / 3) / (float(cfg["-r_convec"]) * side * side) / s.htc - 1) < 1e-8   # HotSpot counts it 1.5x: see to_hotspot


def test_dram_map():
    P = dram.die_map((20, 16), background_W=0.1, active_W=0.3, io_W=0.05, seed=1)
    assert P.shape == (20, 16) and abs(P.sum() - 0.45) < 1e-12 and (P > 0).all()
    lab = dram.layout((20, 16))
    assert (lab == -2).any() and lab.max() + 1 == 16
    with pytest.raises(ValueError):
        dram.die_map((20, 16), 0.1, 0.3, 0.05, mix=np.ones(3) / 3)


def test_dram_window_maps_keep_energy_per_window():
    bank_J = np.arange(3 * 8, dtype=float).reshape(3, 8) * 1e-9
    io_J = np.array([1e-9, 2e-9, 0.0])
    P = dram.window_maps((20, 16), bank_J, io_J, 1e-6)
    assert P.shape == (3, 20, 16)
    assert np.allclose(P.sum((1, 2)) * 1e-6, bank_J.sum(1) + io_J, rtol=1e-12)
    lab = dram.layout((20, 16), banks=(1, 4))
    assert np.allclose(P[1][lab == 5].sum() * 1e-6, bank_J[1, 5]) and (P[:, lab == -1] == 0).all()
    with pytest.raises(ValueError):
        dram.window_maps((20, 16), bank_J[:, :4], io_J, 1e-6)
