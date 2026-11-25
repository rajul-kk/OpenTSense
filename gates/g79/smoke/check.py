"""Check the RTL logs against the independent G81b gate-level logs and activity."""
import argparse
import csv
import hashlib
import json
import re
from itertools import pairwise

from launch import G81B, HERE

RESULT = re.compile(r"^RESULT result=([0-9a-f]{8}) done=([01]) done_cycle=(-?\d+) "
                    r"start=(-?\d+) stop=(-?\d+) cycles=(\d+)$")
MARK = re.compile(r"^MARK (start|stop|phase=\d+) cycle=(\d+)$")
SIGNALS = ("instr_req", "data_req", "data_we", "core_sleep")
INTERVAL = 1000


def read_run(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    results = [line for line in lines if line.startswith("RESULT")]
    marks = [line for line in lines if line.startswith("MARK")]
    if len(results) != 1 or (match := RESULT.fullmatch(results[0])) is None:
        raise ValueError(f"{path}: expected exactly one well-formed RESULT")
    if any(MARK.fullmatch(line) is None for line in marks):
        raise ValueError(f"{path}: malformed MARK lines")
    return match, marks


def activity(path, columns):
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.reader(stream))
    found = {}
    for row in rows[1:] if columns else rows:
        if len(row) != (5 if columns else 17):
            raise ValueError(f"{path}: malformed timeline row")
        cycle, *values = map(int, row)
        if cycle in found or any(value < 0 for value in values):
            raise ValueError(f"{path}: duplicate cycle or negative activity")
        if cycle > 0:
            found[cycle] = values
    return found


def check_stage(stage):
    out = HERE / stage
    program = "crc32" if stage == "slice" else stage
    ref_path = G81B / program / "run.log"
    reference, expected_marks = read_run(ref_path)
    if not expected_marks:
        raise ValueError(f"{ref_path}: missing reference MARK lines")
    result, marks = read_run(out / "run.log")
    metrics = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
    cycles = int(result[6])
    rows = activity(out / "rtl_activity.csv", columns=True)
    checks = {
        "docker_success": metrics["returncode"] == 0,
        "harness_end": "WINDOWS written=0 requested=0 truncated=0" in
        (out / "run.log").read_text(encoding="utf-8").splitlines(),
        "timeline_rows": list(rows) == list(range(INTERVAL, cycles + 1, INTERVAL)),
    }
    if stage == "slice":
        checks["requested_stop"] = result.groups() == ("ffffffff", "0", "-1", "76", "-1", "10000")
        checks["markers"] = marks == [line for line in expected_marks if int(MARK.fullmatch(line)[2]) < cycles]
    else:
        checks["result_and_cycles"] = result.groups() == reference.groups() and reference[2] == "1"
        checks["markers"] = marks == expected_marks
    rate = cycles / metrics["wall_s"] if all(checks.values()) else None
    record = {
        "ok": all(checks.values()), "checks": checks, "rtl": result[0], "gate_level": reference[0],
        "markers_checked": len(marks), "cycles_per_wall_s": rate,
        "wall_s_per_0p5ms_slot": (0.5e-3 / 900e-12) / rate if rate else None,
    }
    (out / "check.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"{stage}: {record}")
    if not record["ok"]:
        raise SystemExit(1)
    if stage == "slice":
        (out / "passed.txt").write_text("SLICE_COMPLETE\n", encoding="utf-8")


def vcd_header(stream):
    scope = []
    symbols = {}
    wanted = (*SIGNALS, "cyc_o", "clk")
    for line in stream:
        fields = line.split()
        if fields[:1] == [b"$scope"]:
            scope.append(fields[2])
        elif fields[:1] == [b"$upscope"]:
            scope.pop()
        elif fields[:1] == [b"$var"] and scope == [b"tb"]:
            name = fields[4].decode()
            if name in wanted:
                symbols[fields[3]] = name
        elif fields[:1] == [b"$enddefinitions"]:
            if set(symbols.values()) != set(wanted):
                raise ValueError("missing gate-level VCD signals")
            return symbols
    raise ValueError("VCD is missing its enddefinitions marker")


def vcd_activity(path):
    """Read settled falling edges once. The first edge primes the previous value."""
    values = {}
    edges = []
    previous_clock = None
    digest = hashlib.sha256()

    def hashed_lines(stream):
        for line in stream:
            digest.update(line)
            yield line

    def edge():
        nonlocal previous_clock
        clock = values.get("clk")
        if previous_clock == b"1" and clock == b"0":
            sample = tuple(int(values[name], 2) for name in ("cyc_o", *SIGNALS))
            edges.append(sample)
        previous_clock = clock

    with path.open("rb") as stream:
        lines = hashed_lines(stream)
        symbols = vcd_header(lines)
        for line in lines:
            lead = line[:1]
            if lead == b"#":
                edge()
            elif lead in (b"0", b"1", b"x", b"z"):
                if name := symbols.get(line[1:].strip()):
                    values[name] = lead
            elif lead == b"b":
                value, symbol = line[1:].split()
                if name := symbols.get(symbol):
                    values[name] = value
        edge()
    if not edges:
        raise ValueError(f"{path}: no falling-edge samples")
    counts = [sum(a != b for a, b in pairwise(channel)) for channel in list(zip(*edges))[1:]]
    return [row[0] for row in edges], counts, digest.hexdigest()


def alignment():
    program = "crc32"
    out = HERE / program
    if json.loads((out / "check.json").read_text(encoding="utf-8"))["ok"] is not True:
        raise ValueError("alignment requires a passing CRC32 program")
    gate_dir = G81B / program
    rtl = activity(out / "rtl_activity.csv", columns=True)
    gate = activity(gate_dir / "timeline.csv", columns=False)
    windows = {int(i): int(cycle) for i, cycle in re.findall(
        r"^WINDOW (\d+) open cycle=(\d+)", (gate_dir / "run.log").read_text(encoding="utf-8"), re.MULTILINE)}
    rows = []
    for i in (0, 10):
        start = windows[i]
        path = gate_dir / f"w{i:03}.vcd"
        cycles, counts, sha = vcd_activity(path)
        end = start + INTERVAL
        delta = [a - b for a, b in zip(rtl[end], counts)]
        ok = (cycles == list(range(start, end)) and any(counts) and all(change in (0, 1) for change in delta))
        rows.append({"input": path.name, "sha256": sha, "start_cycle": start, "row_end_cycle": end,
                     "gate_falling_edges": len(cycles), "gate_transitions_without_first_edge": counts,
                     "rtl_transitions": rtl[end], "rtl_minus_gate": delta, "gate_regional_toggles_sum": sum(gate[end]),
                     "ok": ok})
    record = {"ok": list(rtl) == list(gate) and all(row["ok"] for row in rows),
              "full_rows_rtl": len(rtl), "full_rows_gate": len(gate), "identical_row_indices": list(rtl) == list(gate),
              "signal_order": list(SIGNALS), "sampled_windows": rows}
    (HERE / "alignment.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))
    if not record["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("slice", "crc32", "edn", "idle", "alignment"))
    stage = parser.parse_args().stage
    if stage == "alignment":
        alignment()
    else:
        check_stage(stage)
