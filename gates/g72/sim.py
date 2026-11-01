"""G72 step 2 (opentsense image): Icarus gate-level simulation of the routed ASAP7 ibex and TPU, one VCD window each.
Usage: python gates/g72/sim.py <run dir> <build dir> [ibex windows] [tpu windows]
<run dir>/stdcell holds the pristine ASAP7 models (copied from the ORFS image by run.sh);
<build dir> holds the routed ORFS designs (asap7-ibex, asap7-tpu). Writes <run dir>/sim/ and sim.json.
"""
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from opentsense.power import asap7_models, workloads  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
TB = os.path.join(HERE, "..", "..", "opentsense", "power", "tb")
NETLIST = {"ibex": "asap7-ibex/results/asap7/ibex/base/6_final.v", "tpu": "asap7-tpu/results/asap7/tpu/base/6_final.v"}
VTS = {"ibex": ("R",), "tpu": ("R", "L", "SL")}  # the TPU is mixed-Vt
# ibex: VCD window cycles 1500-2500 (as G30/G34). Kernels 0-3 finish by cycle 27,295, so 30,000 cycles is enough for
# the checksum (G34 ran 80,000); sleep never finishes and stops after the window.
IBEX_MAX = {0: 30000, 1: 30000, 2: 30000, 3: 30000, 4: 2600}


def compile_design(d, run, build):
    w = os.path.join(run, "sim", d)
    os.makedirs(w, exist_ok=True)
    models = asap7_models.build(os.path.join(run, "stdcell"), os.path.join(run, "sim", "models_" + d), VTS[d])
    net = os.path.join(w, "netlist.v")
    open(net, "w", newline="\n").write(open(os.path.join(build, NETLIST[d])).read())
    tb = os.path.join(TB, d + "_tb.v")
    r = subprocess.run(["iverilog", "-g2012", "-o", os.path.join(w, "sim.vvp"), "-s", "tb"] + models + [net, tb],
                       capture_output=True, text=True)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if "warning" not in l.lower()]
    if r.returncode or errs:
        raise RuntimeError(f"iverilog {d}: rc {r.returncode}\n" + "\n".join(errs[:30]))
    return w


def main(run, build, ibex_win=(0, 1, 2, 3, 4), tpu_win=("W1", "W2", "W3")):
    t0 = time.time()
    wi, wt = compile_design("ibex", run, build), compile_design("tpu", run, build)
    workloads.tpu_stimulus(wt)
    hexdir = os.path.join(HERE, "inputs", "ibex_hex")
    jobs = {}
    for k in ibex_win:
        cmd = ["vvp", "-n", "sim.vvp", f"+hex={hexdir}/k{k}.hex", "+win_start=1500", "+win_len=1000",
               f"+vcd=k{k}.vcd", f"+max={IBEX_MAX[k]}"]
        jobs[f"ibex_k{k}"] = (wi, cmd, f"k{k}.log")
    for k in tpu_win:  # TPU window: cycles 600-1600 of 2400 (testbench default, as G36)
        jobs[f"tpu_{k}"] = (wt, ["vvp", "-n", "sim.vvp", f"+hex=stim_{k}.hex", f"+vcd={k}.vcd", f"+out=c_{k}.txt"], f"{k}.log")
    procs = {n: (subprocess.Popen(c, cwd=w, stdout=open(os.path.join(w, log), "w"), stderr=subprocess.STDOUT), time.time())
             for n, (w, c, log) in jobs.items()}
    res = {"compile_s": round(time.time() - t0, 1)}
    exp = workloads.ibex_expected()
    for n, (p, ts) in procs.items():
        rc = p.wait()
        w, _, log = jobs[n]
        r = {"rc": rc, "wall_s": round(time.time() - ts, 1)}
        if n.startswith("ibex"):
            k = int(n[-1])
            got = workloads.ibex_result(os.path.join(w, log))
            r.update(checksum=got and got[0], done=got and got[1], done_cycle=got and got[2], cycles=got and got[3],
                     expected=exp.get(k))
        else:
            k = n.split("_")[1]
            r["rows"], r["rows_match"] = workloads.tpu_check(os.path.join(w, f"c_{k}.txt"), os.path.join(w, f"ref_{k}.json"))
        res[n] = r
        print(n, r, flush=True)
    json.dump(res, open(os.path.join(run, "sim.json"), "w"), indent=1)


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], a[1], *([tuple(int(v) for v in a[2].split(","))] if len(a) > 2 else []),
         *([tuple(a[3].split(","))] if len(a) > 3 else []))
