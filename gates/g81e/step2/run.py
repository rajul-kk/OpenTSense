"""G81e step 2: each program's request trace (step 1) -> H1 or H0 hierarchy -> LPDDR4 controller -> per-window
memory-die energy, with the noise-floor seeds. Computes; `evaluate.py` applies the registered bars.

Per program, H1 (gated): the nominal schedule (no bank hash, refresh phase 0; reported, and the v3 trace) and the
FLOOR_SEEDS schedules, each with its own bank-hash salt and refresh phase (registration: gated values are their mean,
the floor their spread). H0 (reported only): nominal. Every command trace goes through the independent checker (v2).
Energy per window of WINDOW_CPU CPU cycles comes from the fitted model (dry fit rerun of 16 Nov); the nominal H1
trace also goes to DRAMPower once (v3). DRAMPower runs in WSL, as for G50a and the dry fit. G50a's regression (v2)
runs separately: g50a_check.py.

Resumable: a program whose <name>.json exists is not rerun (written last, after its arrays); it records the hashes of
its code, trace and DRAMPower, and a resume from other inputs stops.

Usage (repo root, on the host): python gates/g81e/step2/run.py <step-1 run dir> <out dir>
"""
import gzip
import json
import os
import subprocess
import sys
import time

import numpy as np

sys.path.insert(0, ".")
sys.path.insert(0, os.path.join("gates", "g81e", "dry"))
from opentsense import manifest  # noqa: E402
from opentsense.power import cache, dramctl, dramenergy  # noqa: E402
import fit_energy  # noqa: E402  (its DRAMPower call and memspec path, as the dry fit ran them)

CPU_GHZ = 1.0
WINDOW_CPU = 1000
FLOOR_SEEDS = (1, 2, 3, 4, 5)
FIT = os.path.join("gates", "g81e", "dry", "fit_energy-rerun-20261116.json")
CODE = ["gates/g81e/step2/run.py", FIT.replace(os.sep, "/"), "gates/g81e/dry/fit_energy.py", "opentsense/power/cache.py",
        "opentsense/power/dramctl.py", "opentsense/power/dramenergy.py", "gates/g81b/record/result.json"]


def read_trace(path):
    c, p, w, a = [], [], [], []
    with gzip.open(path, "rt") as f:
        for line in f:
            x = line.split()
            c.append(int(x[0])); p.append(x[1]); w.append(x[2] == "1"); a.append(int(x[3], 16))
    return np.array(c, np.int64), np.array(p), np.array(w, bool), np.array(a, np.int64)


def seed_args(s):
    """Bank-hash salt and refresh phase of seed s (0 = nominal: no hash, phase 0)."""
    return (None, 0) if s == 0 else (s, s * 997 % dramctl.LPDDR4_3200["t"]["REFI"])


def window_energy(tr, model, cycles):
    """Energy per window of WINDOW_CPU cycles over a program of `cycles` CPU cycles, as dramenergy.windows returns
    it, and the trace's length in s. The windows run to the trace's END (the last one partial); a controller backlog
    past the program's end gets windows of its own."""
    dram_per_cpu = 1 / (CPU_GHZ * 1e9) / tr.spec["t"]["tCK"]
    per = WINDOW_CPU * dram_per_cpu
    end, last = int(tr.time.max()), int(tr.time[tr.cmd != "END"].max())
    n = int(np.ceil(max(cycles * dram_per_cpu, last + 1) / per))
    edges = np.append(np.arange(n) * per, end)
    return dramenergy.windows(tr, model, edges), end * tr.spec["t"]["tCK"]


def program(trace, cycles, model, hier):
    """One program under one hierarchy: summary dict, per-window arrays, and the nominal command trace."""
    t0 = time.time()
    res = (cache.h1 if hier == "H1" else cache.h0)(*trace)
    win = res.txn.cycle // WINDOW_CPU
    out = {"txn": int(len(res.txn.cycle)), "stats": {k: vars(v) for k, v in (res.stats or {}).items()}, "seeds": {}}
    arrays, nominal, nw = {}, None, 0
    for s in (0,) + (FLOOR_SEEDS if hier == "H1" else ()):
        salt, phase = seed_args(s)
        tr = dramctl.schedule(res.txn, cpu_ghz=CPU_GHZ, ref_phase=phase, bank_salt=salt, end_cycle=cycles)
        bad = dramctl.check(tr)
        e, dur = window_energy(tr, model, cycles)
        dyn = e["dyn_bank"].sum(1) + e["dyn_io"]
        out["seeds"][s] = {"violations": len(bad), "first_violations": bad[:3], "commands": int(len(tr.time)),
                           "trace_s": dur, "program_s": cycles / (CPU_GHZ * 1e9),
                           "mean_dyn_W": float(dyn.sum() / dur), "mean_total_W": float(e["total"].sum() / dur),
                           "bank_dyn_share": (e["dyn_bank"].sum(0) / max(e["dyn_bank"].sum(), 1e-300)).tolist()}
        arrays[f"s{s}_total_J"], arrays[f"s{s}_dyn_J"] = e["total"], dyn
        nw = max(nw, len(dyn))
        if s == 0:
            nominal = tr
    arrays["txn_per_window"] = np.bincount(win, minlength=nw)
    arrays["miss_per_window"] = np.bincount(win[~res.txn.write], minlength=nw)   # fills only, no write-backs
    out["wall_s"] = round(time.time() - t0, 1)
    return out, arrays, nominal


def drampower_identity():
    """sha256 of the DRAMPower binary fit_energy.drampower runs and of the memspec it reads (in WSL)."""
    r = subprocess.run(["wsl", "-e", "bash", "-c", f"sha256sum ~/tools/DRAMPower/build/bin/cli {fit_energy.MS}"],
                       capture_output=True, text=True, check=True)
    return {os.path.basename(p): h for h, p in (line.split() for line in r.stdout.splitlines())}


def main(step1, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    fit_energy.check_memspec()
    model = dramenergy.Model(**json.load(open(FIT))["model"])
    ref = json.load(open(os.path.join("gates", "g81b", "record", "result.json")))["programs"]
    tools = {**{p: manifest.file_sha256(p) for p in CODE},
             **{f"wsl/{k}": v for k, v in drampower_identity().items()}}
    for name in sorted(ref):
        trace_path = os.path.join(step1, name, "req.txt.gz")
        inputs = {**tools, "trace": manifest.file_sha256(trace_path)}
        done = os.path.join(out_dir, f"{name}.json")
        if os.path.exists(done):
            if json.load(open(done))["inputs_sha256"] != inputs:
                raise RuntimeError(f"{done} was computed from other inputs; move the run aside to start again")
            continue
        trace = read_trace(trace_path)
        cycles = ref[name]["run"]["cycles"]
        res = {"inputs_sha256": inputs}
        for hier in ("H1", "H0"):
            out, arrays, nominal = program(trace, cycles, model, hier)
            if hier == "H1":                                   # v3: one DRAMPower run on the nominal H1 trace
                o = fit_energy.drampower(nominal)
                summed = float(arrays["s0_total_J"].sum())
                out["v3"] = {"drampower_J": o["TotalEnergy"], "windows_J": summed,
                             "rel_err": abs(summed - o["TotalEnergy"]) / o["TotalEnergy"]}
            np.savez_compressed(os.path.join(out_dir, f"{name}_{hier}.npz"), **arrays)
            res[hier] = out
            print(name, hier, out["txn"], "txn", out["wall_s"], "s", flush=True)
        json.dump(res, open(done + ".tmp", "w"), indent=1)
        os.replace(done + ".tmp", done)
    hashes = {**tools, **{f"trace/{n}": manifest.file_sha256(os.path.join(step1, n, "req.txt.gz")) for n in sorted(ref)}}
    manifest.write(os.path.join(out_dir, "manifest.json"),
                   {"gate": "G81e step 2", "cpu_ghz": CPU_GHZ, "window_cpu_cycles": WINDOW_CPU,
                    "floor_seeds": list(FLOOR_SEEDS), "inputs_sha256": hashes})


if __name__ == "__main__":
    main(*sys.argv[1:])
