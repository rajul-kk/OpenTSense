"""Clock facts from a layout's own SDC (ORFS 6_final.sdc), in ps: the testbench takes its timing from here (lint L6)."""
import math
import re


def _values(path, pattern):
    """Every number the pattern captures in the SDC; finding none is an error."""
    found = [float(x) for x in re.findall(pattern, open(path).read())]
    if not found:
        raise ValueError(f"{path}: no match for {pattern!r}")
    return found


def half_ps(path):
    """Half the clock period in whole ps (the testbench toggles the clock every half period). Only clocks on a port
    count: ORFS adds a virtual vclk_* with the same period."""
    periods = _values(path, r"create_clock .*?-period (\S+) \[get_ports")
    if len(periods) > 1:
        raise ValueError(f"{path}: {len(periods)} clocks; the testbench drives one")
    if periods[0] % 2:
        raise ValueError(f"{path}: clock period {periods[0]} ps is not an even number of ps")
    return int(periods[0] // 2)


def input_ps(path):
    """When inputs reach the core: clock latency + the largest input delay, rounded up. Driving inputs on the ideal
    edge races the clock tree (G96)."""
    return math.ceil(_values(path, r"set_clock_latency (\S+)")[0] + max(_values(path, r"set_input_delay (\S+)")))
