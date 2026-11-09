"""Run 3D-ICE, PACT and HotSpot on a stack and read back per-die temperature maps (K, shape (ny, nx), row i = y index i).

All three are expected inside the OpenTSense image: 3D-ICE-Emulator and hotspot on PATH, PACT in $PACT_SRC.
"""
import os
import subprocess
import sys

import numpy as np

from ..stack import to_3dice, to_hotspot, to_pact

ICE_EXE = os.environ.get("ICE_EXE", "3D-ICE-Emulator")
PACT_SRC = os.environ.get("PACT_SRC", "/opt/pact/src")
HOTSPOT_EXE = os.environ.get("HOTSPOT_EXE", "hotspot")


def run_3dice(stack, power, workdir, timeout=7200):
    stk = to_3dice.write(stack, power, workdir)
    r = subprocess.run([ICE_EXE, os.path.basename(stk)], cwd=workdir, capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError("3D-ICE failed:\n" + r.stdout[-1500:] + r.stderr[-1500:])
    nx, ny = stack.grid
    out = {}
    for d in stack.dies:
        T = np.loadtxt(os.path.join(workdir, f"tmap_{d.name}.txt"), comments="%")
        assert T.shape == (ny, nx), f"3D-ICE map for {d.name} has shape {T.shape}, expected {(ny, nx)}"
        out[d.name] = T
    return out


def read_pact(path, nx, ny):
    # PACT grid row r is 3D-ICE row ny-1-r (point-source check in exploratory gate G47)
    return np.loadtxt(path, delimiter=",", ndmin=2)[:, -1].reshape(ny, nx)[::-1]


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
    """HotSpot's grid steady file: "Layer n:" then one "index temperature" line per cell, row 0 at the top edge
    (temperature_grid.c set_bgmap), so rows are flipped to ours. Returns {layer index: (ny, nx)}."""
    out, cur, vals = {}, None, []
    for line in open(path):
        if line.startswith("Layer"):
            if cur in layers:
                out[cur] = np.array(vals).reshape(ny, nx)[::-1]
            cur, vals = int(line.split()[1].rstrip(":")), []
        elif line.strip():
            vals.append(float(line.split()[1]))
    if cur in layers:
        out[cur] = np.array(vals).reshape(ny, nx)[::-1]
    return out


def run_hotspot(stack, power, workdir, timeout=7200):
    paths, src = to_hotspot.write(stack, power, workdir)
    grid = os.path.join(os.path.abspath(workdir), "out.grid.steady")
    cmd = [HOTSPOT_EXE, "-c", paths["config"], "-p", paths["ptrace"], "-grid_layer_file", paths["lcf"], "-model_type", "grid",
           "-detailed_3D", "on", "-steady_file", os.path.join(os.path.abspath(workdir), "out.steady"), "-grid_steady_file", grid]
    r = subprocess.run(cmd, cwd=os.path.abspath(workdir), capture_output=True, text=True, timeout=timeout)
    if r.returncode or not os.path.exists(grid):
        raise RuntimeError("HotSpot failed:\n" + r.stdout[-1500:] + r.stderr[-1500:])
    nx, ny = stack.grid
    T = read_hotspot(grid, set(src.values()), nx, ny)
    return {d: T[li] for d, li in src.items()}
