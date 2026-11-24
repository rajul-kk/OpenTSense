"""Run 3D-ICE, PACT and HotSpot on a stack and read back per-die temperature maps (K, shape (ny, nx), row i = y index i).

All three are expected inside the OpenTSense image: 3D-ICE-Emulator and hotspot on PATH, PACT in $PACT_SRC.
"""
import itertools
import os
import subprocess
import sys
import threading
from dataclasses import replace

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as sla

from ..stack import to_3dice, to_hotspot, to_pact

# PACT's own SuperLU settings, so our solves on its matrix match its steady solution
SUPERLU = dict(permc_spec="MMD_AT_PLUS_A", diag_pivot_thresh=0.001,
               options=dict(Fact="DOFACT", Equil=False, SymmetricMode=True))
ICE_EXE = os.environ.get("ICE_EXE", "3D-ICE-Emulator")
PACT_SRC = os.environ.get("PACT_SRC", "/opt/pact/src")
HOTSPOT_EXE = os.environ.get("HOTSPOT_EXE", "hotspot")


def run_3dice(stack, power, workdir, timeout=7200, transient=None):
    """Steady: {die: (ny, nx)}. With transient = (step_s, slot_s) and (n_slots, ny, nx) power: {die: (n_slots, ny,
    nx)}, the map at the end of each slot (one Tmap per slot, appended; checked in the image, G94, 16 Nov)."""
    stk = to_3dice.write(stack, power, workdir, transient=transient)
    r = subprocess.run([ICE_EXE, os.path.basename(stk)], cwd=workdir, capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError("3D-ICE failed:\n" + r.stdout[-1500:] + r.stderr[-1500:])
    nx, ny = stack.grid
    T = {d.name: to_3dice.read_tmaps(os.path.join(workdir, f"tmap_{d.name}.txt"), ny, nx) for d in stack.dies}
    return _per_die("3D-ICE", stack, power, transient, T)


def _per_die(solver, stack, power, transient, T):
    """{die: (n_dumps, ny, nx)} read back -> {die: (ny, nx)} steady or {die: (n_slots, ny, nx)}, after checking that
    the solver wrote one map per slot."""
    want = 1 if transient is None else stack.check_transient(power)
    if any(len(v) != want for v in T.values()):
        raise RuntimeError(f"{solver} wrote {({d: len(v) for d, v in T.items()})} maps per die, expected {want}")
    return {d: v[0] if transient is None else v for d, v in T.items()}


def read_pact(path, nx, ny):
    return to_pact.rows(np.loadtxt(path, delimiter=",", ndmin=2)[:, -1].reshape(ny, nx))


def run_pact(stack, power, workdir, timeout=7200, capture=False, return_src=False, transient=None):
    """capture=True also saves PACT's matrix and right-hand side as <workdir>/pact.A.npz and pact.b.npy.
    transient = (step_s, slot_s) with (n_slots, ny, nx) maps: see pact_transient."""
    if transient is not None:
        if capture or return_src:
            raise ValueError("capture and return_src apply to steady runs only")
        return pact_transient(stack, power, workdir, *transient, timeout=timeout)
    (lcf, cfg, model), src = to_pact.write(stack, power, workdir)
    grid = os.path.join(os.path.abspath(workdir), "grid.steady")
    pre = [os.path.join(os.path.dirname(__file__), "pact_capture.py"), os.path.join(os.path.abspath(workdir), "pact")] if capture else ["PACT.py"]
    r = subprocess.run([sys.executable] + pre + [os.path.abspath(lcf), os.path.abspath(cfg), os.path.abspath(model), "--gridSteadyFile", grid],
                       cwd=PACT_SRC, capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError("PACT failed:\n" + r.stdout[-1500:] + r.stderr[-1500:])
    nx, ny = stack.grid
    maps = {d: read_pact(f"{grid}.layer{li}", nx, ny) for d, li in src.items()}
    return (maps, src) if return_src else maps


def pact_transient(stack, power, workdir, step, slot, timeout=7200):
    """{die: (n_slots, ny, nx)} at the end of each slot, on PACT's own network: its conductance matrix A (captured
    from one steady PACT run) and its node capacities C (cv x cell volume, as Solid.py), integrated by backward Euler,
    C (T_k+1 - T_k) / step + A T_k+1 = P, from ambient. PACT's own transient path calls Xyce, which the image lacks,
    and its power PWL delays every slot by one slot (G94 draft, 16 Nov)."""
    n_slots = stack.check_transient(power)
    k = round(slot / step)
    if k < 1 or abs(k * step - slot) > 1e-9 * slot:
        raise ValueError(f"slot {slot:g} s must be a whole number of steps {step:g} s")
    _, src = run_pact(stack, {d: P.mean(0) for d, P in power.items()}, workdir, timeout, capture=True, return_src=True)
    A = sp.load_npz(os.path.join(workdir, "pact.A.npz")).tocsc()
    C = to_pact.capacity(stack)
    if len(C) != A.shape[0]:
        raise RuntimeError(f"PACT has {A.shape[0]} nodes, the stack's sublayers {len(C)}")
    Cs = C / step
    lu = sla.splu((sp.diags(Cs) + A).tocsc(), **SUPERLU)
    nx, ny = stack.grid
    rise, b = np.zeros(len(C)), np.zeros(len(C))
    out = {d: np.zeros((n_slots, ny, nx)) for d in src}
    for t in range(n_slots):
        r = to_pact.rhs(stack, {d: P[t] for d, P in power.items()}, src)
        b[:len(r)] = r
        for _ in range(k):
            rise = lu.solve(Cs * rise + b)
        for d, li in src.items():
            out[d][t] = stack.ambient_K + to_pact.rows(rise[li * nx * ny:(li + 1) * nx * ny].reshape(ny, nx))
    return out


def read_hotspot(lines, layers, nx, ny):
    """HotSpot's grid steady or transient dump, as lines: per dump ("t = ..." opens each one in a transient dump),
    "Layer n:" then one "index temperature" line per cell, row 0 at the top edge (temperature_grid.c set_bgmap), so
    rows are flipped to ours. Returns {layer index: (n_dumps, ny, nx)}."""
    out, cur, vals = {l: [] for l in layers}, None, []
    for line in itertools.chain(lines, ["t = end"]):
        if line.startswith(("Layer", "t =")):
            if cur in layers:
                out[cur].append(np.array(vals).reshape(ny, nx)[::-1])
            cur, vals = (int(line.split()[1].rstrip(":")) if line.startswith("Layer") else None), []
        elif cur in layers and line.strip():
            vals.append(float(line.split()[1]))
    return {l: np.array(v) for l, v in out.items()}


def run_hotspot(stack, power, workdir, timeout=7200, transient=None):
    """As run_3dice: steady {die: (ny, nx)}, or {die: (n_slots, ny, nx)} at the end of each slot."""
    paths, src = to_hotspot.write(stack, power, workdir, transient=transient)
    wd = os.path.abspath(workdir)
    cmd = [HOTSPOT_EXE, "-c", paths["config"], "-p", paths["ptrace"], "-grid_layer_file", paths["lcf"], "-model_type", "grid",
           "-detailed_3D", "on"]
    nx, ny = stack.grid
    if transient is None:
        grid = os.path.join(wd, "out.grid.steady")
        r = subprocess.run(cmd + ["-steady_file", os.path.join(wd, "out.steady"), "-grid_steady_file", grid], cwd=wd,
                           capture_output=True, text=True, timeout=timeout)
        if r.returncode or not os.path.exists(grid):
            raise RuntimeError("HotSpot failed:\n" + r.stdout[-1500:] + r.stderr[-1500:])
        with open(grid) as f:
            T = read_hotspot(f, set(src.values()), nx, ny)
    else:
        # The transient dump holds every layer at every row (about 2 MB a row on the 3d stack, tens of GB at G94's
        # finest level), so it is streamed: HotSpot appends each dump to /dev/stdout, parsed here as it arrives.
        with open(os.path.join(wd, "hotspot.err"), "w+") as err:
            p = subprocess.Popen(cmd + ["-o", os.path.join(wd, "out.ttrace"), "-grid_transient_file", "/dev/stdout"],
                                 cwd=wd, stdout=subprocess.PIPE, stderr=err, text=True)
            timer = threading.Timer(timeout, p.kill)
            timer.start()
            try:
                T = read_hotspot(p.stdout, set(src.values()), nx, ny)
            except ValueError:
                T = None                                         # a malformed dump: reported with HotSpot's errors
            finally:
                p.stdout.close()
                rc = p.wait()
                timer.cancel()
            err.seek(0)
            if rc or T is None:
                raise RuntimeError(f"HotSpot failed (rc {rc}):\n" + err.read()[-3000:])
    return _per_die("HotSpot", stack, power, transient, {d: T[li] for d, li in src.items()})


RUNAWAY_RISE_K = 400.0      # a die this far above ambient is past any junction limit: the leakage loop has run away


class Runaway(RuntimeError):
    """solve_kT's leakage loop diverged (a map rose past RUNAWAY_RISE_K or stopped being finite)."""


def solve_kT(run, stack, power, workdir, tol_K=0.01, max_it=20, leak=None):
    """Steady maps with temperature-dependent conductivity (materials with k_T_exp) and, if `leak` is given,
    temperature-dependent power, for any of the three runners. The solvers are linear, so this is a fixed-point
    loop: each layer gets its own copy of every such material at the layer's temperature (a die: the mean over its
    T-dependent cells; a passive layer: the mean of its nearest die or dies), and each die's power is `power` plus
    leak(maps) at the previous solve's maps (electrothermal.map_leakage; the first solve at leak(None), the
    leakage at its reference temperature), until no map moves by more than tol_K. One k per layer, not per cell: a
    hotspot's own lower k is not modelled. A leakage loop that runs away raises Runaway as soon as a map passes
    RUNAWAY_RISE_K above ambient; one that is still moving after max_it solves raises RuntimeError.
    Returns (maps, iterations)."""
    if leak is None and not any(m.k_T_exp for m in stack.materials.values()):
        return run(stack, power, workdir), 1
    T = {l.name: stack.ambient_K for l in stack.layers}
    prev = None
    for it in range(1, max_it + 1):
        P = power
        if leak is not None:
            add = leak(prev)
            P = {d: power[d] + add[d] for d in power}
        maps = run(stack_at(stack, T), P, os.path.join(workdir, f"kT{it}"))
        top = max(float(np.max(m)) for m in maps.values())
        if not np.isfinite(top):          # a numerical failure of the solver or of `leak`, not a physical runaway
            raise RuntimeError(f"solve {it} gave a non-finite temperature map")
        if leak is not None and top >= stack.ambient_K + RUNAWAY_RISE_K:
            raise Runaway(f"leakage loop ran away: {top:.1f} K after {it} solves")
        if prev is not None and max(float(np.abs(maps[d] - prev[d]).max()) for d in maps) < tol_K:
            return maps, it
        prev, T = maps, layer_temps(stack, maps)
    raise RuntimeError(f"k(T) and leakage loop did not settle to {tol_K} K in {max_it} solves")


def layer_temps(stack, maps):
    """{layer: K} from the die maps, as solve_kT uses them."""
    dep = {m for m, v in stack.materials.items() if v.k_T_exp}
    die_T = {}
    for d in stack.dies:
        mask = np.isin(stack.material_map(d), list(dep))
        die_T[d.name] = float(maps[d.name][mask].mean() if mask.any() else maps[d.name].mean())
    at = [i for i, l in enumerate(stack.layers) if l.die]
    out = {}
    for i, l in enumerate(stack.layers):
        gap = min(abs(i - j) for j in at)
        out[l.name] = float(np.mean([die_T[stack.layers[j].name] for j in at if abs(i - j) == gap]))
    return out


def stack_at(stack, T):
    """A copy of the stack whose layers use their own copy of each T-dependent material at T[layer] (K)."""
    mats = dict(stack.materials)
    layers = []
    for l in stack.layers:
        name = lambda m: f"{m}_at_{l.name}" if stack.materials[m].k_T_exp else m  # noqa: E731
        for m in {l.material} | {r.material for r in l.regions}:
            mats[name(m)] = stack.materials[m].at(T[l.name])
        layers.append(replace(l, material=name(l.material),
                              regions=[replace(r, material=name(r.material)) for r in l.regions]))
    return replace(stack, materials=mats, layers=layers)
