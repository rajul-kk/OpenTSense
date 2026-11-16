"""Clock facts from a layout's own SDC (ORFS 6_final.sdc, ASAP7: times in ps), for the testbench (lint L6).
Only the command forms ORFS writes are read; any other option, a value list, or a period too short to be in ps is
refused rather than guessed (L5)."""
import math
import re

MIN_PERIOD_PS = 100   # write_sdc states no unit; an ns SDC (IHP, sky130) has periods of a few units


def _read(path):
    """{command: [(value, clock names, line)]} for the commands this module reads (continuations joined)."""
    with open(path) as f:
        text = re.sub(r"\\\n", " ", f.read())
    allowed = {"create_clock": {"-name", "-period"}, "set_input_delay": {"-clock", "-add_delay"},
               "set_clock_latency": set(), "set_propagated_clock": set()}
    out = {name: [] for name in allowed}
    for name, line in re.findall(rf"^\s*({'|'.join(allowed)})\s+(.*)$", text, re.M):
        toks = line.split()
        nums = [t for t in toks if re.fullmatch(r"-?\d+(\.\d*)?(e-?\d+)?", t)]
        flags = {t for t in toks if t.startswith("-") and t not in nums}
        if flags - allowed[name]:
            raise ValueError(f"{path}: {name}: unsupported option(s) {sorted(flags - allowed[name])} in: {line}")
        clocks = re.search(r"\[get_clocks \{?([^}\]]+)", line)
        if "-clock" in flags and not clocks:
            raise ValueError(f"{path}: {name}: unreadable clock in: {line}")
        out[name].append((float(nums[0]) if nums else None, clocks[1].split() if clocks else [], line))
    return out


def _port_period(path, sdc):
    periods = [v for v, _, l in sdc["create_clock"] if "[get_ports" in l]
    if len(periods) != 1 or periods[0] is None:
        raise ValueError(f"{path}: port clock periods {periods}; the testbench drives one")
    if periods[0] < MIN_PERIOD_PS:
        raise ValueError(f"{path}: clock period {periods[0]} is too short to be ps (an ns SDC?)")
    if periods[0] % 2:
        raise ValueError(f"{path}: clock period {periods[0]} ps is not an even number of ps")
    return periods[0]


def half_ps(path):
    """Half the clock period in whole ps (the testbench toggles the clock every half period). Only clocks on a port
    count: ORFS adds a virtual vclk_* with the same period."""
    return int(_port_period(path, _read(path)) // 2)


def input_ps(path):
    """When inputs reach the core, as signed off: the input clock's latency + the largest input delay, rounded up.
    The input clock is the one every set_input_delay names: ORFS's virtual vclk_*, with the port clock's period and
    not propagated. With no set_clock_latency on it its latency is 0, the SDC default STA used (decision 10, G96 TPU).
    Driving inputs on the ideal edge of the propagated clock instead races the clock tree (G96)."""
    sdc = _read(path)
    period = _port_period(path, sdc)
    delays = sdc["set_input_delay"]
    clocks = {tuple(c) for _, c, _ in delays}
    if not delays or len(clocks) != 1 or len(next(iter(clocks))) != 1 or None in [v for v, *_ in delays]:
        raise ValueError(f"{path}: input delays on {sorted(clocks)}; expected one clock and a value on each")
    clock = next(iter(clocks))[0]
    own = [(v, l) for v, _, l in sdc["create_clock"] if re.search(rf"-name {re.escape(clock)}(\s|$)", l)]
    if len(own) != 1 or "[get_ports" in own[0][1] or any(clock in c for _, c, _ in sdc["set_propagated_clock"]):
        raise ValueError(f"{path}: input clock {clock} is not one ideal virtual clock")
    if own[0][0] != period:
        raise ValueError(f"{path}: input clock period {own[0][0]} differs from the port clock's {period}")
    latency = [(v, c) for v, c, _ in sdc["set_clock_latency"] if clock in c]
    if len(latency) > 1 or any(len(c) != 1 or v is None for v, c in latency):
        raise ValueError(f"{path}: latencies on {clock}: {latency}")
    t = math.ceil(round((latency[0][0] if latency else 0.0) + max(v for v, *_ in delays), 6))
    if not 0 <= t < period:
        raise ValueError(f"{path}: input time {t} ps is not inside the {period} ps cycle")
    return t
