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
    hb = (M == "hybrid_bond").mean()
    assert 0.45 < hb < 0.55 and set(M.ravel()) == {"hybrid_bond", "oxide_bond"}   # L3D 41 of 81 mm2


def test_unknown_interface_key_is_refused():
    with pytest.raises(ValueError, match="r_hbnd"):
        stacks.build("s1", 250, r_hbnd=1e-6)
