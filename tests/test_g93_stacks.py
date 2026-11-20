"""G93's stack builder: every stack validates, every die has a map, totals meet the stated figures."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gates", "g93"))
import stacks  # noqa: E402

TOTAL_W = {"s1": 88.0, "s2": 20.0, "s3": 780.0, "s4": 45.0}   # 85 + 3; 8 x 1.5 + 8; 700 + 4 x 20; 20 + 15 + 10


@pytest.mark.parametrize("name,cell", [("s1", 250), ("s2", 250), ("s3", 500), ("s4", 250)])
def test_stack_builds_with_its_power(name, cell):
    st, P = stacks.build(name, cell)
    assert set(P) == {d.name for d in st.dies}
    st.check_steady(P)
    assert abs(sum(float(v.sum()) for v in P.values()) - TOTAL_W[name]) < 1e-9 * TOTAL_W[name]
    assert all(float(v.min()) >= 0 for v in P.values())


R_KEY = {"tim": ("tim_um", "r_tim"), "hybrid_bond": ("hbond_um", "r_hbond"), "oxide_bond": ("hbond_um", "r_oxbond"),
         "ubump": ("ubump_um", "r_ubump")}


@pytest.mark.parametrize("over", [{}, {"r_hbond": 2.5e-6, "r_ubump": 15e-6, "ubump_um": 15, "tim_um": 80}])
@pytest.mark.parametrize("name,cell", [("s1", 250), ("s2", 250), ("s4", 250)])
def test_every_bonded_layer_carries_its_area_resistance(name, cell, over):
    """thickness / k equals the R'' in force, for the defaults and for a sweep point (thickness and R'' changed)."""
    st, _ = stacks.build(name, cell, **over)
    p = {**stacks.INTERFACES, **over}
    seen = set()
    for layer in st.layers:
        for mat in [layer.material] + [r.material for r in layer.regions]:
            if mat in R_KEY:
                t_key, r_key = R_KEY[mat]
                assert layer.thickness_um == p[t_key]
                assert abs(layer.thickness_um * 1e-6 / st.materials[mat].k - p[r_key]) < 1e-15
                seen.add(mat)
    assert "tim" in seen and seen & {"hybrid_bond", "ubump"}


def test_s1_hybrid_bond_only_under_the_l3d():
    st, _ = stacks.build("s1", 250)
    M = st.material_map(next(layer for layer in st.layers if layer.name == "hbond"))
    hb = (M == "hybrid_bond").sum() / (M != "air").sum()
    assert 0.45 < hb < 0.55 and set(M.ravel()) == {"hybrid_bond", "oxide_bond", "air"}   # L3D 41 of 81 mm2


def test_unknown_interface_key_is_refused():
    with pytest.raises(ValueError, match="r_hbnd"):
        stacks.build("s1", 250, r_hbnd=1e-6)


@pytest.mark.parametrize("name", ["s1", "s2", "s4"])
def test_lid_is_wider_than_the_dies_and_the_sink_carries_r_sink(name):
    """The spreader spans the lid; below it, the die stack sits centred in air; h x area = 1 / r_sink."""
    st, P = stacks.build(name, 500)
    pk = stacks.PACKAGE[name]
    assert all(abs(s - pk["lid_um"]) <= 2 * c for s, c in zip(st.size_um, (st.size_um[0] / st.grid[0],
                                                                           st.size_um[1] / st.grid[1])))
    assert abs(st.htc * st.size_um[0] * st.size_um[1] * 1e-12 * pk["r_sink"] - 1) < 1e-12
    assert st.layers[0].material == "copper" and not st.layers[0].regions
    for layer in st.layers[1:]:
        M = st.material_map(layer)
        assert M[0, 0] == "air" and M[M.shape[0] // 2, M.shape[1] // 2] != "air"
    total = next(iter(P.values()))
    ys, xs = (total > 0).nonzero()
    assert 0 < xs.min() and xs.max() < st.grid[0] - 1 and 0 < ys.min() and ys.max() < st.grid[1] - 1


def test_lid_and_sink_are_parameters():
    st, _ = stacks.build("s1", 500, lid_um=20000, r_sink=0.2)
    assert abs(st.size_um[0] - 20000) < 600 and abs(st.htc * st.size_um[0] * st.size_um[1] * 1e-12 * 0.2 - 1) < 1e-12


def test_subtract_covers_the_rectangle_once_without_the_holes():
    import numpy as np
    rect, holes = [0, 0, 10, 8], [[2, 3, 4, 2], [7, 0, 3, 1]]
    A = np.zeros((8, 10), int)
    for x, y, w, h in stacks.subtract(rect, holes) + holes:
        A[y:y + h, x:x + w] += 1
    assert (A == 1).all()


def test_lid_is_refused_for_the_lidless_s3():
    with pytest.raises(ValueError, match="lid_um"):
        stacks.build("s3", 500, lid_um=40000)


@pytest.mark.parametrize("name", ["s1", "s2", "s3", "s4"])
def test_gated_stacks_carry_an_isotropic_beol_layer_per_die(name):
    st, P = stacks.build(name, 500)
    bare, _ = stacks.build(name, 500, beol_um=0)
    assert len(st.layers) == len(bare.layers) + len(bare.dies)
    m = st.materials["beol"]
    assert (m.k, m.k_lateral) == (stacks.BEOL["beol_k"], None)
    assert all(any(l.name == f"{d.name}_beol" for l in st.layers) for d in bare.dies)
    assert "beol" not in bare.materials
