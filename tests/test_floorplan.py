"""Block floorplans (G93): loading checks, exact rasterisation, the shipped floorplans."""
import glob
import os

import numpy as np
import pytest

from opentsense.stack import floorplan as fp

HERE = os.path.dirname(__file__)
SHIPPED = sorted(glob.glob(os.path.join(HERE, "..", "configs", "floorplans", "*.yaml")))


def plan(blocks, total_W=None, background=0.0):
    return fp.Floorplan("t", (1000.0, 800.0), [fp.Block(*b, "logic", "s", "assumption") for b in blocks],
                        background, total_W, {"s": "test"}).validate()


def test_rasterisation_keeps_power_off_grid():
    p = plan([("a", (123.0, 77.0, 301.0, 250.0), 2.0), ("b", (600.0, 400.0, 333.0, 399.0), 0.5)], background=0.1)
    want = (2.0 * 301 * 250 + 0.5 * 333 * 399 + 0.1 * (1000 * 800 - 301 * 250 - 333 * 399)) * 1e-6
    for grid in ((7, 5), (32, 32), (64, 48)):
        P = p.power_map(grid)
        assert P.shape == grid[::-1] and abs(P.sum() - want) < 1e-12
    P = p.power_map((10, 8))                      # 100 um cells: cell (row 1, col 2) lies wholly inside block a
    assert abs(P[1, 2] - 2.0 * 100 * 100 * 1e-6) < 1e-15


def test_total_scales_every_block_by_one_factor():
    p = plan([("a", (0.0, 0.0, 500.0, 800.0), 2.0), ("b", (500.0, 0.0, 500.0, 800.0), 1.0)], total_W=3.0)
    P = p.power_map((10, 8))
    assert abs(P.sum() - 3.0) < 1e-12 and abs(P[:, :5].sum() / P[:, 5:].sum() - 2.0) < 1e-12


@pytest.mark.parametrize("blocks,msg", [
    ([("a", (0.0, 0.0, 600.0, 800.0), 1.0), ("b", (500.0, 0.0, 500.0, 800.0), 1.0)], "overlap"),
    ([("a", (900.0, 0.0, 200.0, 800.0), 1.0)], "not inside"),
])
def test_bad_layouts_are_refused(blocks, msg):
    with pytest.raises(ValueError, match=msg):
        plan(blocks)


def test_unknown_source_and_grade_are_refused():
    with pytest.raises(ValueError, match="unknown source"):
        fp.Floorplan("t", (10.0, 10.0), [fp.Block("a", (0, 0, 5, 5), 1.0, "x", "nope", "primary")], sources={}).validate()
    with pytest.raises(ValueError, match="grade"):
        fp.Floorplan("t", (10.0, 10.0), [fp.Block("a", (0, 0, 5, 5), 1.0, "x", "s", "guess")], sources={"s": ""}).validate()


def test_density_from_maps(tmp_path):
    p = tmp_path / "m.npz"
    np.savez(p, die_um=np.array([0.0, 0.0, 100.0, 50.0]), W1=np.full((4, 4), 1e-4))
    assert abs(fp.density_from_maps(p, "W1") - 16e-4 / (100 * 50 * 1e-6)) < 1e-12


@pytest.mark.parametrize("path", SHIPPED, ids=[os.path.basename(p) for p in SHIPPED])
def test_shipped_floorplans_tile_their_die_and_meet_their_total(path):
    f = fp.load(path)
    w, h = f.size_um
    assert abs(sum(b.rect_um[2] * b.rect_um[3] for b in f.blocks) - w * h) < 1e-6 * w * h   # no unaccounted area
    assert abs(f.power_map((64, 64)).sum() - f.total_W) < 1e-9 * f.total_W


def test_total_zero_gives_no_power_and_nothing_to_scale_is_refused():
    p = plan([("a", (0.0, 0.0, 500.0, 800.0), 2.0)], total_W=0.0)
    assert not p.power_map((10, 8)).any()
    with pytest.raises(ValueError, match="total_W"):
        plan([("a", (0.0, 0.0, 500.0, 800.0), 0.0)], total_W=5.0)
    with pytest.raises(ValueError, match="total_W"):
        plan([("a", (0.0, 0.0, 500.0, 800.0), 1.0)], total_W=-1.0)


def test_misspelt_block_key_is_refused(tmp_path):
    f = tmp_path / "f.yaml"
    f.write_text("name: t\nsize_um: [10, 10]\nsources: {s: x}\nblocks:\n"
                 "  - {name: a, rect_um: [0, 0, 5, 5], W_mm2: 1, kind: x, source: s, grade: primary, wmm2: 3}\n")
    with pytest.raises(ValueError, match="wmm2"):
        fp.load(str(f))
