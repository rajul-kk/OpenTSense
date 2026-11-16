"""G96: one window simulated twice with Icarus, zero-delay and delay-aware, with the same testbench, clock and input time.
Usage: python gates/g96/sim.py <run dir> <layout results dir> <ibex|tpu> <delay netlist>
<run dir>/stdcell holds the pristine ASAP7 models. Writes <run dir>/{zero,delay}.{vcd,log} and sim.json.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
from opentsense.power import asap7_models, sdc, workloads  # noqa: E402

TB = os.path.join(HERE, "..", "..", "opentsense", "power", "tb")
VTS = {"ibex": ("R",), "tpu": ("R", "L", "SL")}


def main(run, res, d, delay_net):
    half, in_ps = sdc.half_ps(os.path.join(res, "6_final.sdc")), sdc.input_ps(os.path.join(res, "6_final.sdc"))
    models = asap7_models.build(os.path.join(run, "stdcell"), os.path.join(run, "models"), VTS[d])
    if d == "ibex":
        args = [f"+hex={HERE}/../g72/inputs/ibex_hex/k0.hex", "+win_start=1500", "+win_len=1000", "+max=16000"]
    else:
        workloads.tpu_stimulus(run, ("W1",))
        args = ["+hex=stim_W1.hex"]   # window cycles 600-1600, the testbench default (G36, G72)
    procs = {}
    for v, net in (("zero", os.path.join(res, "6_final.v")), ("delay", delay_net)):
        c = subprocess.run(["iverilog", "-g2012", "-o", f"{v}.vvp", "-s", "tb", *models, net, os.path.join(TB, f"{d}_tb.v")],
                           cwd=run, capture_output=True, text=True)
        errs = [l for l in (c.stdout + c.stderr).splitlines() if "warning" not in l.lower()]
        if c.returncode or errs:
            raise RuntimeError(f"iverilog {v}: rc {c.returncode}\n" + "\n".join(errs[:30]))
        cmd = ["vvp", "-n", f"{v}.vvp", *args, f"+vcd={v}.vcd", f"+out=c_{v}.txt", f"+half_ps={half}", f"+in_ps={in_ps}"]
        procs[v] = subprocess.Popen(cmd, cwd=run, stdout=open(os.path.join(run, f"{v}.log"), "w"), stderr=subprocess.STDOUT)
    res_ = {"half_ps": half, "in_ps": in_ps}
    for v, p in procs.items():
        r = {"rc": p.wait()}
        if d == "ibex":
            got = workloads.ibex_result(os.path.join(run, f"{v}.log"))
            r.update(checksum=got and got[0], done=got and got[1], done_cycle=got and got[2], expected=workloads.ibex_expected()[0])
            r["ok"] = r["done"] == 1 and r["checksum"] == r["expected"]
        else:
            r["rows"], r["rows_match"] = workloads.tpu_check(os.path.join(run, f"c_{v}.txt"), os.path.join(run, "ref_W1.json"))
            r["ok"] = r["rows"] == 616 == r["rows_match"]
        res_[v] = r
        print(v, r, flush=True)
    json.dump(res_, open(os.path.join(run, "sim.json"), "w"), indent=1)


if __name__ == "__main__":
    main(*sys.argv[1:5])
