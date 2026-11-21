"""Goal 11's stack variants: one BEOL layer on each die's source face under its powered silicon only; the board
coefficient spread over the dies' footprint; per-region summaries that skip air."""
import os
import sys

import numpy as np
import pytest

sys.path[:0] = [os.path.join(os.path.dirname(__file__), "..", "gates", "g93"),
                os.path.join(os.path.dirname(__file__), "..", "gates", "g93", "sens")]
import beol_board  # noqa: E402
import stacks  # noqa: E402


@pytest.mark.parametrize("name", ["s1", "s2", "s3", "s4"])
def test_beol_sits_on_each_source_face_under_powered_silicon(name):
    st, P = stacks.build(name, 500, beol_um=0)
    b = beol_board.variant(st, P, "beol_aniso")
    assert len(b.layers) == len(st.layers) + len(st.dies)
    names = [l.name for l in b.layers]
    for d in st.dies:
        i, j = names.index(d.name), names.index(f"{d.name}_beol")
        assert j == (i - 1 if d.source_side == "top" else i + 1)
        beol = b.material_map(b.layers[j]) == "beol"
        assert beol.any() and (np.asarray(P[d.name])[~beol] == 0).all()   # all of the die's power is over BEOL
    m = b.materials["beol"]
    assert (m.k, m.k_lateral) == (beol_board.K_V, beol_board.K_L)
    assert beol_board.variant(st, P, "beol_iso").materials["beol"].k_lateral is None


def test_s3_logic_die_gets_one_beol_layer_not_nine():
    st, P = stacks.build("s3", 500, beol_um=0)
    b = beol_board.variant(st, P, "beol_aniso")
    logic = max(beol_board.silicon(st, st.dies[0]), key=lambda r: r[2] * r[3])   # the largest rectangle: logic
    j0, j1, i0, i1 = b.cells(logic)
    maps = [b.material_map(l)[i0:i1, j0:j1] for l in b.layers if l.name.endswith("_beol")]
    assert sum(1 for m in maps if (m == "beol").any()) == 1
    assert all(set(np.unique(m)) <= {"beol", "silicon"} for m in maps)   # no mould slab across the logic column


@pytest.mark.parametrize("name", ["s1", "s3"])
def test_board_coefficient_is_one_over_r_jb_across_the_die_footprint(name):
    st, P = stacks.build(name, 500, beol_um=0)
    b = beol_board.variant(st, P, "board_lo")
    area = sum(w * h for _, _, w, h in beol_board.silicon(st, st.layers[-1])) * 1e-12
    assert abs(b.opposite_htc * area * beol_board.R_JB[0] - 1) < 1e-12
    if name == "s1":
        assert area < 0.2 * st.size_um[0] * st.size_um[1] * 1e-12   # the CCD's footprint, not the 30 mm lid
    assert st.opposite_htc == 0 and b.layers == st.layers


def test_summary_reads_only_inside_powered_silicon():
    st, P = stacks.build("s1", 500, beol_um=0)
    T = {d.name: np.full(st.grid[::-1], st.ambient_K + 10.0) for d in st.dies}
    for d in st.dies:
        T[d.name][0, 0] = st.ambient_K + 1000.0          # a hot air cell outside the die must not count
    s = beol_board.summary(st, T, P)
    assert set(s) == {d.name for d in st.dies}
    assert all(v["peak_rise_K"] == pytest.approx(10.0) and v["max_gradient_K_per_mm"] == 0 for v in s.values())


def test_cache_key_depends_on_cell_size():
    assert beol_board.key(500) != beol_board.key(250)
