"""Solver-level checks for G93a (run inside the image; skipped where the tools are missing).
These are plumbing checks on small stacks, not the G93a bars: orientation of each solver's output, the three solvers
agreeing roughly on a stack with lateral regions and with a bottom sink, and the observed-cell response operator."""
import os
import shutil

import numpy as np
import pytest

from opentsense.stack import model
from opentsense.thermal import response
from opentsense.thermal.run import run_3dice, run_hotspot, run_pact

CFG = os.path.join(os.path.dirname(__file__), "..", "configs", "stacks", "single_die.yaml")
need = pytest.mark.skipif(not (shutil.which("hotspot") and shutil.which("3D-ICE-Emulator") and os.path.isdir(os.environ.get("PACT_SRC", "/opt/pact/src"))),
                          reason="thermal tools not installed")


def small(side="top", regions=True):
    s = model.load(CFG)
    s.grid = (16, 12)
    s.size_um = (1600.0, 1200.0)
    s.materials["mould"] = model.Material(0.8, 1.8e6)
    s.sink_side = side
    for l in s.layers:
        l.n_sub = 1
    if regions:
        d = s.dies[0]
        d.material = "mould"
        d.regions = [model.Region("silicon", (200.0, 200.0, 1000.0, 800.0))]
    return s.validate()


def point(s, i, j, w=0.05):
    P = np.zeros(s.grid[::-1])
    P[i, j] = w
    return {s.dies[0].name: P}


@need
@pytest.mark.parametrize("run", [run_3dice, run_pact, run_hotspot])
def test_orientation(tmp_path, run):
    s = small(regions=False)
    T = run(s, point(s, 2, 12), tmp_path)[s.dies[0].name]       # row 2 (near y = 0), column 12
    assert T.shape == (12, 16) and np.unravel_index(np.argmax(T), T.shape) == (2, 12)


@need
@pytest.mark.parametrize("side", ["top", "bottom"])
def test_three_solvers_regions(tmp_path, side):
    s = small(side)
    P = {s.dies[0].name: s.place(np.full((8, 10), 2e-3), (200.0, 200.0, 1000.0, 800.0))}
    T = {f.__name__: f(s, P, tmp_path / f.__name__)[s.dies[0].name] for f in (run_3dice, run_pact, run_hotspot)}
    rise = {k: v - s.ambient_K for k, v in T.items()}
    peak = {k: v.max() for k, v in rise.items()}
    assert min(peak.values()) > 0.5
    # HotSpot (detailed 3D) and 3D-ICE both put the node at the cell centre: same discretisation, so equal to output
    # precision (3D-ICE prints 0.001 K). PACT puts it at the bottom face: one node per layer here, so only rough
    # agreement (G71: 2.4 to 3.3 K apart at one node per layer, within 0.42 K once refined)
    assert np.abs(T["run_hotspot"] - T["run_3dice"]).max() < 0.01, peak
    assert max(peak.values()) / min(peak.values()) < 1.3, peak


@need
def test_hotspot_regions_matter(tmp_path):
    a, b = small(regions=True), small(regions=False)
    P = {a.dies[0].name: a.place(np.full((8, 10), 2e-3), (200.0, 200.0, 1000.0, 800.0))}
    ta = run_hotspot(a, P, tmp_path / "a")[a.dies[0].name]
    tb = run_hotspot(b, P, tmp_path / "b")[b.dies[0].name]
    assert ta.max() > tb.max() + 0.01                            # mould around the die must change the answer


@need
def test_observed_response(tmp_path):
    s = small()
    nx, ny = s.grid
    d = s.dies[0].name
    basis = [point(s, 3, 4), point(s, 6, 9)]
    R = response.build(s, basis, tmp_path / "full")
    m = np.zeros((ny, nx), bool); m[2:5, 3:7] = True
    Ro = response.build(s, basis, tmp_path / "obs", observe={d: m})
    assert Ro.shape == (2, m.sum())
    assert np.allclose(Ro, R[:, 0][:, m], rtol=1e-10, atol=1e-12)


def two_sink(opposite_htc, bond=None):
    """single_die.yaml plus a 200 um substrate below the die (k 20, or `bond`) and, optionally, a bottom sink."""
    s = model.load(CFG)
    s.grid = (8, 8)
    s.materials["sub"] = bond or model.Material(20.0, 1.6e6)
    s.layers.append(model.Layer("substrate", "sub", 200.0, n_sub=8))
    for l, n in zip(s.layers, (10, 3, 6, 8)):
        l.n_sub = n
    s.opposite_htc = opposite_htc
    return s.validate()


@need
def test_3dice_bottom_sink_equals_1d_analytic(tmp_path):
    """Uniform power: no lateral flow, so the source temperature is T_amb + q (R_up || R_down) exactly (nodes at
    sublayer centres: the source node sits half a source layer from its faces)."""
    q = 1e6                                                     # W/m^2, 1 W over 1 mm^2
    for h_bot in (0.0, 5e3):
        s = two_sink(h_bot)
        nx, ny = s.grid
        P = {"die0": np.full((ny, nx), q * 1e-6 / (nx * ny))}
        T = run_3dice(s, P, tmp_path / f"h{h_bot:g}")["die0"]
        die = s.dies[0]
        r_up = 500e-6 / 400 + 25e-6 / 4 + die.bulk_um * 1e-6 / 130 + 0.5 * die.source_um * 1e-6 / 130 + 1 / s.htc
        r_dn = 0.5 * die.source_um * 1e-6 / 130 + 200e-6 / 20 + 1 / h_bot if h_bot else np.inf
        want = s.ambient_K + q / (1 / r_up + 1 / r_dn)
        assert abs(T.mean() - want) < 0.01 * (want - s.ambient_K), (h_bot, T.mean(), want)


@need
def test_3dice_reads_lateral_and_vertical_conductivity_the_right_way_round(tmp_path):
    """A point source over a substrate cooled from below: high in-plane k spreads the hotspot, high vertical k
    keeps it sharp. If the x, y, z order were wrong the two would swap."""
    flat = {}
    for name, (k_v, k_lat) in {"lateral": (5.0, 500.0), "vertical": (500.0, 5.0), "iso": (500.0, 500.0)}.items():
        s = two_sink(5e4, model.Material(k_v, 1.6e6, k_lat))
        s.htc = 1e2                                             # most heat leaves through the bottom
        T = run_3dice(s, point(s, 4, 4), tmp_path / name)["die0"]
        flat[name] = float(T.max() - T.mean())
    assert flat["lateral"] < flat["vertical"], flat
    s = two_sink(5e4, model.Material(500.0, 1.6e6, 500.0))
    s.htc = 1e2
    iso = run_3dice(s, point(s, 4, 4), tmp_path / "iso_plain")["die0"]
    assert abs(float(iso.max() - iso.mean()) - flat["iso"]) < 1e-3   # k_lateral == k is the isotropic material


@need
def test_kT_loop_runs_in_all_three_and_heats_the_die(tmp_path):
    from opentsense.thermal.run import solve_kT
    s = small(regions=True)
    P = {s.dies[0].name: s.place(np.full((8, 10), 2e-2), (200.0, 200.0, 1000.0, 800.0))}
    base = run_3dice(s, P, tmp_path / "base")[s.dies[0].name]
    s.materials["silicon"] = model.Material(130.0, 1.63566e6, None, 1.3)
    got = {}
    for f in (run_3dice, run_pact, run_hotspot):
        maps, it = solve_kT(f, s, P, str(tmp_path / f.__name__), tol_K=1e-3)
        got[f.__name__] = maps[s.dies[0].name]
        assert 2 <= it < 20
    assert got["run_3dice"].max() > base.max() + 0.01             # hotter silicon conducts worse
    assert np.abs(got["run_hotspot"] - got["run_3dice"]).max() < 0.01   # as in test_three_solvers_regions
