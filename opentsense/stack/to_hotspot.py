"""Stack -> HotSpot 7 grid-model input (config, layer configuration file, one floorplan per layer, power trace).

HotSpot's layer file (.lcf) lists layers from the one farthest from the sink (layer 0) to the one next to it, and
HotSpot always adds two package layers after the last one: a heat spreader and a heat sink, square, of side
s_spreader / s_sink. The sink cells connect to ambient through r_convec * s_sink^2 / (cell area), i.e. a per-cell
heat transfer coefficient h = 1 / (r_convec * s_sink^2). To match 3D-ICE's and PACT's per-cell HTC on the sink face,
both package layers are made 1 nm thick (copper): their vertical resistance and lateral conductance are then
negligible against any real layer (to be confirmed in the G93a dry run).
The sink's convection share is counted 1.5 times by HotSpot's detailed-3D model: the sink cell's rz includes
r_convec * s_sink^2 / (cell area) (populate_R_model_grid), the sink-to-ambient branch uses that rz in full
(build_transient_grid_matrix: "all nodes are connected to the ambient", R = rz), and the spreader-to-sink branch
uses rz_spreader/2 + rz_sink/2 (find_res, detailed_3D branch). So r_convec = (2/3) / (htc * s_sink^2) gives a total
cell-to-ambient resistance of 1 / (htc * cell area), as in 3D-ICE and PACT (checked on a small stack, G93a).
Both package layers must be at least as large as the chip, and strictly larger: HotSpot builds peripheral package nodes
from (side - chip size), and an exactly chip-sized spreader makes the system singular (SuperLU then leaves the power
vector in place, and the grid dump prints power, not temperature). The side is 1.001 x the chip's longer side; with
1 nm layers the result moved by < 1e-3 K between 1.0001x and 1.1x (G93a dry run).

Every layer's floorplan covers our grid with rectangles of whole cells, one unit per rectangle of equal material (and,
on a source layer, equal power per cell in every slot); HotSpot's grid (grid_rows x grid_cols) is our grid, so with
grid_map_mode avg each cell gets exactly its own material and power, as with one unit per cell. Per-cell units hit
HotSpot's limits on large stacks: MAX_UNITS = 8192 per floorplan and trace, and an n_units^2 wire-density matrix per
floorplan (flp.c), about 620 MB per layer at 8800 cells (G93 S3). Block floorplans and regions need a few dozen.
With regions, each unit carries its own volumetric heat capacity and resistivity, which needs -detailed_3D on (used
always, for one code path). Dies: bulk sublayers carry no power, the source layer does.
The power trace is one line of names and one line of values per slot over every source unit; the image's HotSpot
reads lines of up to LINE_SIZE - 1 characters (raised to 1048576 by the image patch, G93a amendment 1; stock: 65536).

Transient (G94): power maps are (n_slots, ny, nx), one trace row per slot, sampling_intvl = the slot. HotSpot picks
its own internal steps inside an interval, so the step of transient = (step, slot) is not used. It starts from
init_temp (ambient here; HotSpot's default is 333.15 K) and dumps the grid after each row (-grid_transient_file,
6 decimals with the image patch's amendment 2).
HotSpot multiplies every capacitance by C_FACTOR = 0.333, "fitting factor to match floworks (due to lumping)"
(temperature.h, RCutil.c getcap), so cv is written divided by it: the network then holds the physical heat capacity,
as in 3D-ICE and PACT. Without it HotSpot heated about 3x too fast (G94 probe, 16 Nov: 7.77 against 5.60 K at 12 ms on
a small stack; 5.58 K with it). Steady results do not depend on cv.
"""
import os

import numpy as np

LINE_SIZE = 1048576
MAX_UNITS = 8192  # units per floorplan and per power trace (flp.h, hotspot.c)
C_FACTOR = 0.333


def rectangles(labels):
    """Cover an (ny, nx) label array with rectangles of one label each: [(i0, j0, h, w)], greedy, rows first."""
    ny, nx = labels.shape
    free = np.ones((ny, nx), bool)
    out = []
    for i0 in range(ny):
        for j0 in range(nx):
            if not free[i0, j0]:
                continue
            v, w = labels[i0, j0], 1
            while j0 + w < nx and free[i0, j0 + w] and labels[i0, j0 + w] == v:
                w += 1
            h = 1
            while i0 + h < ny and free[i0 + h, j0:j0 + w].all() and (labels[i0 + h, j0:j0 + w] == v).all():
                h += 1
            free[i0:i0 + h, j0:j0 + w] = False
            out.append((i0, j0, h, w))
    return out


def _flp(path, stack, layer, prefix, P=None):
    """One unit per rectangle of equal material (and, on a source layer, equal power in every slot, P: (n, ny, nx)).
    Returns (unit names, (n_slots, n_units) unit powers) for a source layer."""
    nx, ny = stack.grid
    cx, cy = stack.size_um[0] * 1e-6 / nx, stack.size_um[1] * 1e-6 / ny
    M = stack.material_map(layer)
    key = np.unique(M, return_inverse=True)[1].reshape(ny, nx)[None]
    if P is not None:
        key = np.concatenate([key, P])
    labels = np.unique(key.reshape(len(key), -1).T, axis=0, return_inverse=True)[1].reshape(ny, nx)
    out, names, watts = ["# <unit> <width> <height> <left-x> <bottom-y> <volumetric heat capacity> <resistivity>"], [], []
    for i0, j0, h, w in rectangles(labels):
        m, name = stack.materials[M[i0, j0]], f"{prefix}{i0}_{j0}"
        out.append(f"{name}\t{w * cx:.9e}\t{h * cy:.9e}\t{j0 * cx:.9e}\t{i0 * cy:.9e}\t{m.cv / C_FACTOR:.6e}\t{1 / m.k:.6e}")
        names.append(name)
        if P is not None:
            watts.append(P[:, i0:i0 + h, j0:j0 + w].sum((1, 2)))
    open(path, "w", newline="\n").write("\n".join(out) + "\n")
    return names, (np.array(watts).T if P is not None else None)


def write(stack, power, workdir, transient=None):
    """power: {die layer name: (ny, nx) array in W}, or (n_slots, ny, nx) with transient = (step_s, slot_s).
    Returns (paths dict, {die: HotSpot layer index of its source})."""
    if transient is None:
        stack.check_steady(power)
        power = {k: np.asarray(v)[None] for k, v in power.items()}
    else:
        stack.check_transient(power)
    stack.check_one_sink("HotSpot")
    workdir = os.path.abspath(workdir)
    os.makedirs(workdir, exist_ok=True)
    nx, ny = stack.grid
    L, W = stack.size_um[0] * 1e-6, stack.size_um[1] * 1e-6
    side = 1.001 * max(L, W)
    lcf, src, names, rows, li = [], {}, [], [], 0
    for l, kind, th in stack.sublayers():
        m = stack.materials[l.material]
        flp = f"L{li}.flp"
        unit_names, watts = _flp(os.path.join(workdir, flp), stack, l, f"L{li}_", power[l.name] if kind == "src" else None)
        lcf += [f"# {l.name} {kind}".rstrip(), str(li), "Y", "Y" if kind == "src" else "N",
                f"{m.cv / C_FACTOR:.6e}", f"{1 / m.k:.6e}", f"{th * 1e-6:.9e}", flp, ""]
        if kind == "src":
            src[l.name] = li
            names += unit_names
            rows.append(watts)
        li += 1
    if len(names) > MAX_UNITS:
        raise ValueError(f"{len(names)} power units exceed HotSpot's MAX_UNITS ({MAX_UNITS}); use a coarser grid")
    cfg = {
        "ambient": f"{stack.ambient_K:.3f}", "init_temp": f"{stack.ambient_K:.3f}",
        "grid_rows": ny, "grid_cols": nx, "grid_map_mode": "avg",
        "s_sink": f"{side:.9e}", "t_sink": "1e-9", "k_sink": "400.0", "p_sink": "3.45e6",
        "s_spreader": f"{side:.9e}", "t_spreader": "1e-9", "k_spreader": "400.0", "p_spreader": "3.45e6",
        "r_convec": f"{(2 / 3) / (stack.htc * side * side):.9e}", "c_convec": "1e-12",
        "model_secondary": 0, "leakage_used": 0, "package_model_used": 0,
    }
    if transient is not None:
        cfg["sampling_intvl"] = f"{transient[1]:.9e}"
    paths = {k: os.path.join(workdir, f) for k, f in (("config", "hotspot.config"), ("lcf", "stack.lcf"), ("ptrace", "power.ptrace"))}
    open(paths["config"], "w", newline="\n").write("".join(f"\t\t-{k}\t{v}\n" for k, v in cfg.items()))
    open(paths["lcf"], "w", newline="\n").write("\n".join(lcf))
    lines = ["\t".join(names)] + ["\t".join(f"{v:.9e}" for v in r) for r in np.hstack(rows)]
    longest = max(len(l) for l in lines)
    if longest + 1 >= LINE_SIZE:
        raise ValueError(f"HotSpot power trace line of {longest} characters exceeds HotSpot's LINE_SIZE ({LINE_SIZE}); "
                         "use a coarser grid or fewer source layers")
    open(paths["ptrace"], "w", newline="\n").write("\n".join(lines) + "\n")
    return paths, src
