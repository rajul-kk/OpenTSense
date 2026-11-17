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
