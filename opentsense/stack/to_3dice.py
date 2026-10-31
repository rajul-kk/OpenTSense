"""Stack -> 3D-ICE 4.0 input (.stk plus one .flp per die).

3D-ICE works in micrometres, so k is in W/(um K) and cv in J/(um^3 K). Power maps are (ny, nx) arrays in W,
row i = y index i from the die's lower edge. Each grid cell becomes one floorplan element.
Stack element names get an S_ prefix because some words (e.g. spreader) are 3D-ICE keywords.
"""
import math
import os


def write_flp(path, P, cell_x, cell_y):
    ny, nx = P.shape
    out = []
    for i in range(ny):
        for j in range(nx):
            out += [f"E{i}_{j}:", f"  position {j * cell_x:.6f}, {i * cell_y:.6f} ;",
                    f"  dimension {cell_x:.6f}, {cell_y:.6f} ;", f"  power values {P[i, j]:.9e} ;", ""]
    open(path, "w", newline="\n").write("\n".join(out))


def write(stack, power, workdir):
    """power: {die layer name: (ny, nx) array in W}. Returns the .stk path; maps go to tmap_<die>.txt."""
    os.makedirs(workdir, exist_ok=True)
    L, W = stack.size_um
    nx, ny = stack.grid
    # 3D-ICE takes floor(chip / cell) cells, so an exact L/nx can round down to nx-1. Round the cell down to 1 nm;
    # the elements then cover all but < nx nm of the chip.
    cx, cy = math.floor(L / nx * 1000) / 1000, math.floor(W / ny * 1000) / 1000
    s = []
    for m, v in stack.materials.items():
        s += [f"material {m} :", f"   thermal conductivity {v.k * 1e-6:.6e} ;", f"   volumetric heat capacity {v.cv * 1e-18:.6e} ;"]
    s += ["top heat sink :", f"   heat transfer coefficient {stack.htc * 1e-12:.6e} ;", f"   temperature {stack.ambient_K:.3f} ;"]
    s += ["dimensions :", f"  chip length {L:.6f} , width {W:.6f} ;", f"  cell length {cx:.6f} , width {cy:.6f} ;"]
    for l in stack.layers:
        if l.die:
            s += [f"die D_{l.name} :", f"   layer {l.thickness_um - l.source_um:.6f} {l.material} ;", f"   source {l.source_um:.6f} {l.material} ;"]
        else:
            s += [f"layer L_{l.name} :", f"   height {l.thickness_um:.6f} ;", f"   material {l.material} ;"]
    s += ["stack:"]
    for l in stack.layers:
        if l.die:
            write_flp(os.path.join(workdir, f"{l.name}.flp"), power[l.name], cx, cy)
            s += [f'   die S_{l.name} D_{l.name} floorplan "{l.name}.flp" ;']
        else:
            s += [f"   layer S_{l.name} L_{l.name} ;"]
    s += ["solver:", "  steady ;", f"  initial temperature {stack.ambient_K:.3f} ;", "output:"]
    s += [f'  Tmap ( S_{d.name}, "tmap_{d.name}.txt", final ) ;' for d in stack.dies]
    path = os.path.join(workdir, "stack.stk")
    open(path, "w", newline="\n").write("\n".join(s) + "\n")
    return path
