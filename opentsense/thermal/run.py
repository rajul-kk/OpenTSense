"""Run 3D-ICE and PACT on a stack and read back per-die temperature maps (K, shape (ny, nx), row i = y index i).

Both tools are expected inside the OpenTSense image: 3D-ICE-Emulator on PATH and PACT in $PACT_SRC.
"""
import os
import subprocess
import sys

import numpy as np

from ..stack import to_3dice, to_pact

ICE_EXE = os.environ.get("ICE_EXE", "3D-ICE-Emulator")
PACT_SRC = os.environ.get("PACT_SRC", "/opt/pact/src")


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


def run_pact(stack, power, workdir, timeout=7200):
    (lcf, cfg, model), src = to_pact.write(stack, power, workdir)
    grid = os.path.join(os.path.abspath(workdir), "grid.steady")
    r = subprocess.run([sys.executable, "PACT.py", os.path.abspath(lcf), os.path.abspath(cfg), os.path.abspath(model), "--gridSteadyFile", grid],
                       cwd=PACT_SRC, capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError("PACT failed:\n" + r.stdout[-1500:] + r.stderr[-1500:])
    nx, ny = stack.grid
    return {d: read_pact(f"{grid}.layer{li}", nx, ny) for d, li in src.items()}
