"""Stack -> 3D-ICE 4.0 input (.stk, one .flp per die, one .lyt per layer with regions).

3D-ICE works in micrometres, so k is in W/(um K) and cv in J/(um^3 K). Power maps are (ny, nx) arrays in W,
row i = y index i from the die's lower edge. Each grid cell becomes one floorplan element.
Stack element names get an S_ prefix because some words (e.g. spreader) are 3D-ICE keywords.
A layer with regions gets a layout file: the layer's material is the base, and each rectangle of a layout overrides
it (3D-ICE 4.0 `layout`, cells not covered keep the base material). A die with regions uses pre-declared layer types
for its bulk and source, because only a declared layer can carry a layout.
Transient (G94): power maps are (n_slots, ny, nx); each element gets one power value per slot, the solver runs
`transient step S, slot T`, and each die's Tmap is written at the end of every slot (`read_tmaps` splits the file).
"""
import math
import os

import numpy as np


def write_flp(path, P, cell_x, cell_y):
    """P: (ny, nx) steady, or (n_slots, ny, nx) with one power value per slot."""
    P3 = P[None] if np.ndim(P) == 2 else P
    _, ny, nx = P3.shape
    out = []
    for i in range(ny):
        for j in range(nx):
            vals = ", ".join(f"{v:.9e}" for v in P3[:, i, j])
            out += [f"E{i}_{j}:", f"  position {j * cell_x:.6f}, {i * cell_y:.6f} ;",
                    f"  dimension {cell_x:.6f}, {cell_y:.6f} ;", f"  power values {vals} ;", ""]
    open(path, "w", newline="\n").write("\n".join(out))


def read_tmaps(path, ny, nx):
    """All maps in a Tmap file as (n, ny, nx): numeric rows of nx values, comment lines (%) skipped, ny rows per map."""
    rows = [list(map(float, l.split())) for l in open(path) if l.strip() and not l.lstrip().startswith("%")]
    if any(len(r) != nx for r in rows) or len(rows) % ny:
        raise ValueError(f"{path}: {len(rows)} rows, not a whole number of {ny} x {nx} maps")
    return np.array(rows).reshape(-1, ny, nx)


def write_lyt(path, stack, layer, cx, cy):
    """Rectangles on the (rounded) 3D-ICE cell grid, grouped by material."""
    by = {}
    for r in layer.regions:
        j0, j1, i0, i1 = stack.cells(r.rect_um)
        by.setdefault(r.material, []).append(f"   rectangle ( {j0 * cx:.6f}, {i0 * cy:.6f}, {(j1 - j0) * cx:.6f}, {(i1 - i0) * cy:.6f} ) ;")
    out = []
    for m, rects in by.items():
        out += [f"{m} :"] + rects + [""]
    open(path, "w", newline="\n").write("\n".join(out))


def write(stack, power, workdir, transient=None):
    """power: {die layer name: (ny, nx) array in W}, or (n_slots, ny, nx) with transient = (step_s, slot_s).
    Returns the .stk path; maps go to tmap_<die>.txt (the final map, or one per slot)."""
    if transient is None:
        stack.check_steady(power)
    else:
        step, slot = transient
        if not 0 < step <= slot:
            raise ValueError("transient needs 0 < step <= slot")
        # the slot must be a whole number of steps as written (the review reads 3D-ICE as truncating slot / step;
        # to confirm in the image in G94's dry run)
        ratio = float(f"{slot:.6e}") / float(f"{step:.6e}")
        if math.floor(ratio) != round(ratio) or abs(ratio - round(ratio)) > 1e-9 * ratio:
            raise ValueError(f"slot / step = {ratio!r} must be a whole number")
        if any(np.ndim(power[d.name]) != 3 for d in stack.dies):
            raise ValueError("transient power maps must be (n_slots, ny, nx)")
        if len({len(power[d.name]) for d in stack.dies}) != 1:
            raise ValueError("transient power maps must have the same number of slots on every die")
    os.makedirs(workdir, exist_ok=True)
    L, W = stack.size_um
    nx, ny = stack.grid
    # 3D-ICE takes floor(chip / cell) cells, so an exact L/nx can round down to nx-1. Round the cell down to 1 nm;
    # the elements then cover all but < nx nm of the chip.
    cx, cy = math.floor(L / nx * 1000) / 1000, math.floor(W / ny * 1000) / 1000
    s = []
    for m, v in stack.materials.items():
        s += [f"material {m} :", f"   thermal conductivity {v.k * 1e-6:.6e} ;", f"   volumetric heat capacity {v.cv * 1e-18:.6e} ;"]
    s += [f"{stack.sink_side} heat sink :", f"   heat transfer coefficient {stack.htc * 1e-12:.6e} ;", f"   temperature {stack.ambient_K:.3f} ;"]
    s += ["dimensions :", f"  chip length {L:.6f} , width {W:.6f} ;", f"  cell length {cx:.6f} , width {cy:.6f} ;"]
    # 3D-ICE's grammar wants every layer definition before the first die definition
    for l in stack.layers:
        lyt = []
        if l.regions:
            write_lyt(os.path.join(workdir, f"{l.name}.lyt"), stack, l, cx, cy)
            lyt = [f'   layout "{l.name}.lyt" ;']
        if not l.die:
            s += [f"layer L_{l.name} :", f"   height {l.thickness_um / l.n_sub:.6f} ;", f"   material {l.material} ;"] + lyt
        elif l.regions:
            s += [f"layer LB_{l.name} :", f"   height {l.bulk_um / l.n_sub:.6f} ;", f"   material {l.material} ;"] + lyt
            s += [f"layer LS_{l.name} :", f"   height {l.source_um:.6f} ;", f"   material {l.material} ;"] + lyt
    for l in stack.dies:
        # within a die, 3D-ICE lists layers top first, like the stack
        if l.regions:
            bulk = [f"   layer LB_{l.name} ;"] * l.n_sub
            src = [f"   source LS_{l.name} ;"]
        else:
            bulk = [f"   layer {l.bulk_um / l.n_sub:.6f} {l.material} ;"] * l.n_sub
            src = [f"   source {l.source_um:.6f} {l.material} ;"]
        s += [f"die D_{l.name} :"] + (bulk + src if l.source_side == "bottom" else src + bulk)
    s += ["stack:"]
    for l in stack.layers:
        if l.die:
            write_flp(os.path.join(workdir, f"{l.name}.flp"), power[l.name], cx, cy)
            s += [f'   die S_{l.name} D_{l.name} floorplan "{l.name}.flp" ;']
        else:
            s += [f"   layer S_{l.name}_{k} L_{l.name} ;" for k in range(l.n_sub)]
    mode = "  steady ;" if transient is None else f"  transient step {transient[0]:.6e}, slot {transient[1]:.6e} ;"
    when = "final" if transient is None else "slot"
    s += ["solver:", mode, f"  initial temperature {stack.ambient_K:.3f} ;", "output:"]
    s += [f'  Tmap ( S_{d.name}, "tmap_{d.name}.txt", {when} ) ;' for d in stack.dies]
    path = os.path.join(workdir, "stack.stk")
    open(path, "w", newline="\n").write("\n".join(s) + "\n")
    return path
