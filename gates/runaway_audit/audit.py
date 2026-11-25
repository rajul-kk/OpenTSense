"""Runaway audit (task runaway-audit, 20 Nov 2026): do the runaway margins recorded by G95, G101 and G103 hold under
the confirmed classifier?

Those gates bracketed the margin s* with `runaway.critical_scale` while Newton's runaway exit assumed leakage convex in
T; G92e's tables are not (C6-3, task runaway-fix). The fixed `runaway.classify` confirms every runaway by fixed-point
iteration from ambient and certifies every converged verdict with an upper solution. This audit re-classifies, with
the gates' own cases (`gates/g95/sweep.py`'s load, unchanged) and solver settings:
- G95 hot (= G103's TT control) and G103's SS/FF corners: the recorded s_hi (expected: runaway) and s_lo (expected:
  converged); if s_hi is not runaway, the margin is re-bracketed upward from s_lo with the fixed code;
- G101's perturbed tile sets (TT, hot): only s* = sqrt(a b) is recorded, so the probes are s* (1 + rtol) (at or above
  the recorded a, b: expected runaway) and s* (1 - rtol) (expected converged).
Verdicts refer to R with round-off negatives set to 0 and to T_cap = 1000 K (`runaway` docstring). Statuses only:
no 1/(1 - rho) is applied to a fixed-point endpoint (Sol RF-4). G101's Recorder is not used (it replaces `_rho`).
Never re-run to pass: this is a finding for the owner, not an amendment.
A window whose instance tables are not monotone in T (`classify` refuses them) is probed through monotone lower and
upper envelopes (`envelopes`); its status is then runaway, converged or undecided, and it is not re-bracketed.

Usage (in the image, repo root): python gates/runaway_audit/audit.py <out.json> [unit ...]
A unit is <kit>:<corner> (corner tt, ss or ff); default all nine. audit.json is rewritten after every window; a
finished unit is skipped on rerun only if its hashed inputs are unchanged; "complete" (the end marker) needs all nine.
"""
import hashlib
import importlib.util
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
spec = importlib.util.spec_from_file_location("g95_sweep", os.path.join(ROOT, "gates", "g95", "sweep.py"))
sweep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sweep)
from opentsense.thermal import electrothermal as et
from opentsense.thermal import runaway

T_AMB = sweep.AMBIENT["hot"]
KITS = {"ihp": ("/b/g53/ihp-sg13g2-ibex/inst_loc.csv", "configs/stacks/g92_ihp.yaml"),       # run_sweep.sh
        "asap7": ("/b/asap7/asap7-ibex/inst_loc.csv", "configs/stacks/g92b_asap7.yaml"),
        "asap7_lvt": ("/b/asap7/asap7-ibex/inst_loc.csv", "configs/stacks/g92b_asap7.yaml")}
CORNERS = ("tt", "ss", "ff")
G101_SCALE = 1.1         # G101's SCALE on a tile set
GRID_C = np.union1d(sweep.TEMPS, np.arange(25.0, 740.0, 5.0))   # envelope grid, deg C: past T_cap (726.85 C)


def read_json(path):
    with open(path) as fh:
        return json.load(fh)


def run_dir(kit, corner):
    return f"gates/g92e/runs/main/{kit}" if corner == "tt" else f"gates/g103/runs/main/{kit}/{corner}"


def recorded(kit, corner):
    """{window: (s_lo, s_hi)} as the gate recorded them (TT: G95's hot sweep; corners: G103's margin.json)."""
    p = (f"gates/g95/runs/main/{kit}/sweep_{kit}.json" if corner == "tt"
         else f"gates/g103/runs/main/{kit}/{corner}/margin.json")
    w = read_json(p)["windows"]
    return {k: (v["s_lo"], v["s_hi"]) for k, v in w.items()}, p


def g101_sets(kit):
    """{window: {set: (tiles, s_star)}} from G101's run output."""
    d = read_json(f"gates/g101/runs/main/{kit}/g101_{kit}.json")["windows"]
    return {w: {n: (s["tiles"], s["s_star"]) for n, s in v["sets"].items()} for w, v in d.items()}


def envelopes(L):
    """Non-decreasing lower and upper envelopes of instance tables that are not monotone in T, on GRID_C.

    `runaway`'s certificates need H(T) = T_amb + R (dyn + P(T)) monotone; some G103 corner libraries have instances
    whose leakage falls with T (asap7 SS/FF, asap7_lvt FF). GRID_C holds the table temperatures, so the original
    model is exactly log-linear between grid points, and log-linear interpolation is increasing in both end values:
    lo <= original <= hi at every grid point carries to every temperature in [25 C, GRID_C[-1]], which covers
    [T_amb, T_cap]. lo = min over later grid points, hi = max over earlier ones; both are non-decreasing.
    - hi has an upper solution U <= T_cap: H maps [T_amb, U] into itself (H <= H_hi, H_hi monotone), so H has a fixed
      point at or below T_cap (Brouwer): an operating point exists ("converged"; no claim that the loop reaches it).
    - lo's fixed-point iteration from ambient passes T_cap: every fixed point T* <= T_cap of H would bound each
      iterate (T* = H(T*) >= H_lo(T*) >= H_lo(T_n)), so none exists ("runaway")."""
    m = et.LeakModel(sweep.TEMPS, L, np.zeros(len(L), int), 1)
    F = np.stack([m.inst(np.full(len(L), t)) for t in GRID_C], axis=1)
    return np.minimum.accumulate(F[:, ::-1], axis=1)[:, ::-1], np.maximum.accumulate(F, axis=1)


def monotone(L):
    return not np.any(np.diff(L, axis=1) < 0)


def probe(R, dyn, model):
    """model: one LeakModel, or (lower, upper) envelope models; the status is then the bracket's: runaway if the
    lower envelope runs away, converged if the upper one converges, else undecided."""
    t = time.time()
    if isinstance(model, tuple):
        lo, hi = (runaway.classify(R, dyn, m, T_AMB, **sweep.NEWTON) for m in model)
        status = ("inconsistent" if lo.status == "runaway" and hi.status == "converged" else "runaway"
                  if lo.status == "runaway" else "converged" if hi.status == "converged" else "undecided")
        return {"status": status, "envelope": [lo.status, hi.status], "wall_s": round(time.time() - t, 2)}
    o = runaway.classify(R, dyn, model, T_AMB, **sweep.NEWTON)
    return {"status": o.status, "picard_it": int(o.picard_it), "iterations": int(o.iterations),
            "peak_K": float(np.max(o.T)) if np.all(np.isfinite(o.T)) else None, "wall_s": round(time.time() - t, 2)}


def audit_window(R, NT, L, dyn, tl, s_lo, s_hi, sets=None):
    env = None if monotone(L) else envelopes(L)

    def mk(s, f=1.0):
        if env is None:
            return et.LeakModel(sweep.TEMPS, L * f, tl, NT, s)
        return tuple(et.LeakModel(GRID_C, E * f, tl, NT, s) for E in env)
    r = {"s_lo": s_lo, "s_hi": s_hi, "non_monotone_instances": int(np.any(np.diff(L, axis=1) < 0, axis=1).sum()),
         "at_s_hi": probe(R, dyn, mk(s_hi)), "at_s_lo": probe(R, dyn, mk(s_lo))}
    r["s_hi_holds"] = r["at_s_hi"]["status"] == "runaway"
    r["s_lo_certified"] = r["at_s_lo"]["status"] == "converged"
    if not r["s_hi_holds"] and env is None:   # critical_scale needs one monotone model
        lo = s_lo if r["s_lo_certified"] else 1e-2
        try:                                  # RA-1: a failed rebracket is recorded; the other probes still run
            a, b, n = runaway.critical_scale(R, dyn, mk, T_AMB, lo=lo, hi=1e6, rtol=sweep.RTOL, **sweep.NEWTON)
            r["rebracket"] = {"s_lo": a, "s_hi": b, "probes": n,
                              "rel_change": float(np.sqrt(a * b) / np.sqrt(s_lo * s_hi) - 1)}
        except (RuntimeError, ValueError) as e:
            r["rebracket"] = {"error": f"{type(e).__name__}: {e}"}
    if sets:
        r["g101_sets"] = {}
        for name, (tiles, s_star) in sets.items():
            f = np.where(np.isin(tl, tiles), G101_SCALE, 1.0)[:, None]
            up, down = probe(R, dyn, mk(s_star * (1 + sweep.RTOL), f)), probe(R, dyn, mk(s_star * (1 - sweep.RTOL), f))
            r["g101_sets"][name] = {"s_star": s_star, "above": up, "below": down,
                                        "holds": up["status"] == "runaway" and down["status"] == "converged"}
    return r


def write(res, out):
    tmp = out + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(res, fh, indent=1)
    os.replace(tmp, out)


def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def unit_inputs(kit, corner):
    """Every file a unit's verdicts depend on, hashed (RA-2): the code, the recorded endpoints, the stack and the
    power tables (the placement file sits in the read-only build mount and is named, not hashed)."""
    run = run_dir(kit, corner)
    files = [os.path.abspath(__file__), sweep.__file__, runaway.__file__, et.__file__, recorded(kit, corner)[1],
             KITS[kit][1]] + sorted(os.path.join(run, "power", f) for f in os.listdir(os.path.join(run, "power")))
    if corner == "tt":
        files += [os.path.join(run, "result.json"), f"gates/g101/runs/main/{kit}/g101_{kit}.json"]
    return {"placement": KITS[kit][0], "sha256": {os.path.relpath(f).replace(os.sep, "/"): sha(f) for f in files}}


def main(out, units=None):
    every = [f"{k}:{c}" for k in KITS for c in CORNERS]
    units = units or every
    res = read_json(out) if os.path.exists(out) else {"T_amb_K": T_AMB, "units": {}}
    res.pop("complete", None)
    res["requested"] = units                  # RA-3: complete only when all nine units are done
    for u in units:
        kit, corner = u.split(":")
        inputs = unit_inputs(kit, corner)
        old = res["units"].get(u, {})
        if old.get("done"):
            if old.get("inputs") != inputs:   # RA-2: a kept unit is valid only for the inputs that made it
                raise SystemExit(f"{u}: inputs changed since it was audited; start a fresh out dir")
            continue
        rec, src = recorded(kit, corner)
        loc, stack = KITS[kit]
        t = time.time()
        R, NT, cases = sweep.load(run_dir(kit, corner), loc, stack, os.path.join(os.path.dirname(out), "op", u.replace(":", "_")))
        if corner == "tt":
            sweep.check_against_g92e(run_dir(kit, corner), R, NT, cases, "hot")   # the same R and cases as the gates
        sets = g101_sets(kit) if corner == "tt" else {}
        U = res["units"][u] = {"recorded_from": src, "inputs": inputs, "operator_s": round(time.time() - t, 1),
                               "R_min": float(R.min()), "windows": {}}
        for w, (L, dyn, tl) in cases.items():
            U["windows"][w] = audit_window(R, NT, L, dyn, tl, *rec[w], sets=sets.get(w))
            print(u, w, U["windows"][w]["at_s_hi"]["status"], U["windows"][w]["at_s_lo"]["status"], flush=True)
            write(res, out)
        U["done"] = True
        write(res, out)
    if all(res["units"].get(u, {}).get("done") for u in every):
        res["complete"] = True
    write(res, out)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:] or None)
