"""G94 case construction: shapes, the pulse switching off, and the programs sequence's power scale."""
import importlib.util
import os

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("g94_cases", os.path.join(ROOT, "gates", "g94", "cases.py"))
cases = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cases)


def test_step_holds_the_seed_maps_every_slot():
    P, M = cases.step("3d", 0, 4), cases.maps("3d", 0)
    for d in M:
        assert P[d].shape == (4,) + M[d].shape and np.array_equal(P[d][3], M[d])


def test_pulse_is_the_step_then_zero():
    P = cases.pulse("25d_regions", 0, 5, 2)["chiplets"]
    assert P[1].sum() > 0 and not P[2:].any()


@pytest.mark.skipif(not os.path.isdir(os.path.join(ROOT, "gates", "g81b", "runs", "main")),
                    reason="needs G81b's timelines (git-ignored run output)")
def test_programs_holds_each_program_for_its_dwell_at_g84_scale():
    P, order = cases.programs(1, 3)
    cpu = P["bot"]
    assert cpu.shape[0] == 3 * len(order) and "idle" not in order and len(set(order)) == len(order)
    assert all(np.array_equal(cpu[3 * i], cpu[3 * i + 2]) for i in range(len(order)))
    dark = 0.4                                                          # G84: 0.4 W outside the active block
    block = cpu.sum((1, 2))[::3] - dark
    assert block.min() > 0 and 0.5 < np.median(block) / cases.CPU_BLOCK_W < 2
    assert np.allclose(P["top"], P["top"][0])                           # TPU die constant


solve_spec = importlib.util.spec_from_file_location("g94_solve", os.path.join(ROOT, "gates", "g94", "solve.py"))
solve = importlib.util.module_from_spec(solve_spec)
solve_spec.loader.exec_module(solve)


def test_case_list_follows_the_dies():
    assert cases.names("3d") == cases.names("3d_bottom") == ("step", "pulse", "programs")
    assert cases.names("25d_regions") == ("step", "pulse")


def test_refinement_levels_3dice_cannot_parse_are_refused_before_solving():
    solve.check_level(0.005, 7)
    with pytest.raises(ValueError):
        solve.check_level(0.005, 8)


def test_on_grid_takes_the_coarser_levels_row_ends():
    fine = np.arange(1, 17)                        # level 2: 4 rows per slot, 4 slots
    assert list(solve.on_grid(fine, 2, 0)) == [4, 8, 12, 16]
    assert list(solve.on_grid(fine, 2, 1)) == [2, 4, 6, 8, 10, 12, 14, 16]


def test_t63_recovers_a_first_order_time_constant():
    dt, tau = 1e-4, 0.043
    t = dt * (np.arange(5000) + 1)
    assert abs(solve.t63(3.0 * (1 - np.exp(-t / tau)), dt) - tau) < 1e-3 * tau
