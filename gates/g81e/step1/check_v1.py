"""G81e (v1), trace validity: each program's traced run ends as G81b's did (cycles, result), and in every G81b window
the trace holds exactly the requests the gate-level VCD shows.

The VCD side samples tb's signals just before each rising clock edge (the values the testbench's always block reads)
and counts instruction requests and non-MMIO data requests per cycle; the trace side counts its lines at the cycles
the VCD covers. Usage (repo root): python gates/g81e/step1/check_v1.py <step-1 run dir> <out json>
"""
import gzip
import json
import os
import re
import sys
from collections import Counter

G81B = os.path.join("gates", "g81b")
SIGNALS = ("clk", "rst_n", "instr_req", "data_req", "data_addr", "cyc")


def vcd_requests(path):
    """{cycle: number of requests} over the cycles the window VCD covers."""
    ids, state, prev, out = {}, {}, None, {}
    with open(path) as f:
        scope = []
        for line in f:
            line = line.lstrip()                                            # Verilator indents the header
            if line.startswith("$scope"):
                scope.append(line.split()[2])
            elif line.startswith("$upscope"):
                scope.pop()
            elif line.startswith("$var") and scope[-1:] == ["tb"]:          # TOP.tb in Verilator's VCD
                p = line.split()
                if p[4] in SIGNALS:
                    ids[p[3]] = p[4]
            elif line.startswith("$enddefinitions"):
                break
        for line in f:
            c = line[0]
            if c == "#":
                prev = dict(state)
            elif c in "01" and line[1:].strip() in ids:
                name = ids[line[1:].strip()]
                if name == "clk" and c == "1" and prev and prev.get("rst_n") == 1 and "cyc" in prev:
                    mmio = (prev["data_addr"] >> 8) & 0x3FF == 0x3FF
                    out[prev["cyc"]] = prev["instr_req"] + (prev["data_req"] and not mmio)
                state[name] = int(c)
            elif c == "b":
                v, i = line[1:].split()
                if i in ids:
                    state[ids[i]] = int(v.replace("x", "0").replace("z", "0"), 2)
    return out


def trace_requests(path):
    n = Counter()
    with gzip.open(path, "rt") as f:
        for line in f:
            n[int(line.split(" ", 1)[0])] += 1
    return n


def main(run, out):
    ref = json.load(open(os.path.join(G81B, "record", "result.json")))["programs"]
    res = {}
    for prog, r in sorted(ref.items()):
        d = os.path.join(run, prog)
        m = re.search(r"RESULT result=(\w+) done=(\d+) .* cycles=(\d+)", open(os.path.join(d, "run.log")).read())
        ended = m is not None and (m.group(1), int(m.group(2)), int(m.group(3))) == (r["run"]["result"], r["run"]["done"],
                                                                                         r["run"]["cycles"])
        tr = trace_requests(os.path.join(d, "req.txt.gz"))
        vdir = os.path.join(G81B, "runs", "main", prog)
        windows = []
        for v in sorted(f for f in os.listdir(vdir) if re.fullmatch(r"w\d+\.vcd", f)):
            got = vcd_requests(os.path.join(vdir, v))
            vcd_n, tr_n = sum(got.values()), sum(tr[c] for c in got)
            windows.append(dict(vcd=v, cycles=len(got), vcd_requests=vcd_n, trace_requests=tr_n))
        ok_w = len(windows) == r["windows"] and all(w["cycles"] > 0 and w["vcd_requests"] == w["trace_requests"] for w in windows)
        res[prog] = dict(ended_as_g81b=ended, windows=windows, windows_match=ok_w, requests=sum(tr.values()), v1=ended and ok_w)
        print(prog, res[prog]["v1"], res[prog]["requests"], flush=True)
    res = dict(programs=res, v1=len(res) == len(ref) and all(p["v1"] for p in res.values()))
    json.dump(res, open(out, "w"), indent=1)
    print("v1:", res["v1"])


if __name__ == "__main__":
    main(*sys.argv[1:])
