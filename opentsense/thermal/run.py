"""Run 3D-ICE, PACT and HotSpot on a stack and read back per-die temperature maps (K, shape (ny, nx), row i = y index i).

All three are expected inside the OpenTSense image: 3D-ICE-Emulator and hotspot on PATH, PACT in $PACT_SRC.
"""
import os
import subprocess
import sys
from dataclasses import replace

import numpy as np

from ..stack import to_3dice, to_hotspot, to_pact

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
    out = {}
    for d in stack.dies:
        T = to_3dice.read_tmaps(os.path.join(workdir, f"tmap_{d.name}.txt"), ny, nx)
        want = 1 if transient is None else len(power[d.name])
        if len(T) != want:
            raise RuntimeError(f"3D-ICE wrote {len(T)} maps for {d.name}, expected {want}")
        out[d.name] = T[0] if transient is None else T
    return out


def read_pact(path, nx, ny):
    return to_pact.rows(np.loadtxt(path, delimiter=",", ndmin=2)[:, -1].reshape(ny, nx))


def run_pact(stack, power, workdir, timeout=7200, capture=False, return_src=False):
    """capture=True also saves PACT's matrix and right-hand side as <workdir>/pact.A.npz and pact.b.npy."""
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


def read_hotspot(path, layers, nx, ny):
    """HotSpot's grid steady or transient file: per dump ("t = ..." opens each one in a transient file), "Layer n:"
    then one "index temperature" line per cell, row 0 at the top edge (temperature_grid.c set_bgmap), so rows are
    flipped to ours. Returns {layer index: (n_dumps, ny, nx)}."""
    out, cur, vals = {l: [] for l in layers}, None, []
    for line in list(open(path)) + ["t = end"]:
        if line.startswith(("Layer", "t =")):
            if cur in layers:
                out[cur].append(np.array(vals).reshape(ny, nx)[::-1])
            cur, vals = (int(line.split()[1].rstrip(":")) if line.startswith("Layer") else None), []
        elif line.strip():
            vals.append(float(line.split()[1]))
    return {l: np.array(v) for l, v in out.items()}


def run_hotspot(stack, power, workdir, timeout=7200, transient=None):
    """As run_3dice: steady {die: (ny, nx)}, or {die: (n_slots, ny, nx)} at the end of each slot."""
    paths, src = to_hotspot.write(stack, power, workdir, transient=transient)
    wd = os.path.abspath(workdir)
    grid = os.path.join(wd, "out.grid.steady" if transient is None else "out.grid.transient")
    if os.path.exists(grid):
        os.remove(grid)                                          # HotSpot appends to the transient file
    cmd = [HOTSPOT_EXE, "-c", paths["config"], "-p", paths["ptrace"], "-grid_layer_file", paths["lcf"], "-model_type", "grid",
           "-detailed_3D", "on"]
    cmd += (["-steady_file", os.path.join(wd, "out.steady"), "-grid_steady_file", grid] if transient is None else
            ["-o", os.path.join(wd, "out.ttrace"), "-grid_transient_file", grid])
    r = subprocess.run(cmd, cwd=wd, capture_output=True, text=True, timeout=timeout)
    if r.returncode or not os.path.exists(grid):
        raise RuntimeError("HotSpot failed:\n" + r.stdout[-1500:] + r.stderr[-1500:])
    nx, ny = stack.grid
    T = read_hotspot(grid, set(src.values()), nx, ny)
    want = 1 if transient is None else stack.check_transient(power)
    if any(len(v) != want for v in T.values()):
        raise RuntimeError(f"HotSpot wrote {[len(v) for v in T.values()]} maps per die, expected {want}")
    return {d: T[li][0] if transient is None else T[li] for d, li in src.items()}


def solve_kT(run, stack, power, workdir, tol_K=0.01, max_it=20):
    """Steady maps with temperature-dependent conductivity (materials with k_T_exp), for any of the three runners.
    The solvers are linear, so this is a fixed-point loop: each layer gets its own copy of every such material at
    the layer's temperature (a die: the mean over its T-dependent cells; a passive layer: the mean of its nearest
    die or dies), until no map moves by more than tol_K. One k per layer, not per cell: a hotspot's own lower k is
    not modelled. Returns (maps, iterations)."""
    if not any(m.k_T_exp for m in stack.materials.values()):
        return run(stack, power, workdir), 1
    T = {l.name: stack.ambient_K for l in stack.layers}
    prev = None
    for it in range(1, max_it + 1):
        maps = run(stack_at(stack, T), power, os.path.join(workdir, f"kT{it}"))
        if prev is not None and max(float(np.abs(maps[d] - prev[d]).max()) for d in maps) < tol_K:
            return maps, it
        prev, T = maps, layer_temps(stack, maps)
    raise RuntimeError(f"k(T) loop did not settle to {tol_K} K in {max_it} solves")


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
