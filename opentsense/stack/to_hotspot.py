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

Every layer's floorplan is our grid of cells (one unit per cell), so HotSpot's grid (grid_rows x grid_cols) maps one
cell to one unit. With regions, each unit carries its own volumetric heat capacity and resistivity, which needs
-detailed_3D on (used always, for one code path). Dies: bulk sublayers carry no power, the source layer does.
The power trace is one line of names and one of values over every source cell; the image's HotSpot reads lines of up
to LINE_SIZE - 1 characters (raised to 1048576 by the image patch, G93a amendment 1; stock HotSpot: 65536).
"""
import os

LINE_SIZE = 1048576


def _flp(path, stack, layer, prefix):
    nx, ny = stack.grid
    L, W = stack.size_um[0] * 1e-6, stack.size_um[1] * 1e-6
    cx, cy = L / nx, W / ny
    M = stack.material_map(layer)
    out = ["# <unit> <width> <height> <left-x> <bottom-y> <volumetric heat capacity> <resistivity>"]
    for i in range(ny):
        for j in range(nx):
            m = stack.materials[M[i, j]]
            out.append(f"{prefix}{i}_{j}\t{cx:.9e}\t{cy:.9e}\t{j * cx:.9e}\t{i * cy:.9e}\t{m.cv:.6e}\t{1 / m.k:.6e}")
    open(path, "w", newline="\n").write("\n".join(out) + "\n")


def write(stack, power, workdir):
    """power: {die layer name: (ny, nx) array in W}. Returns (paths dict, {die: HotSpot layer index of its source})."""
    stack.check_steady(power)
    workdir = os.path.abspath(workdir)
    os.makedirs(workdir, exist_ok=True)
    nx, ny = stack.grid
    L, W = stack.size_um[0] * 1e-6, stack.size_um[1] * 1e-6
    side = 1.001 * max(L, W)
    lcf, src, names, values, li = [], {}, [], [], 0
    for l, kind, th in stack.sublayers():
        m = stack.materials[l.material]
        flp = f"L{li}.flp"
        prefix = f"L{li}_"
        _flp(os.path.join(workdir, flp), stack, l, prefix)
        lcf += [f"# {l.name} {kind}".rstrip(), str(li), "Y", "Y" if kind == "src" else "N",
                f"{m.cv:.6e}", f"{1 / m.k:.6e}", f"{th * 1e-6:.9e}", flp, ""]
        if kind == "src":
            src[l.name] = li
            P = power[l.name]
            for i in range(ny):
                for j in range(nx):
                    names.append(f"{prefix}{i}_{j}")
                    values.append(f"{P[i, j]:.9e}")
        li += 1
    cfg = {
        "ambient": f"{stack.ambient_K:.3f}", "init_temp": f"{stack.ambient_K:.3f}",
        "grid_rows": ny, "grid_cols": nx, "grid_map_mode": "avg",
        "s_sink": f"{side:.9e}", "t_sink": "1e-9", "k_sink": "400.0", "p_sink": "3.45e6",
        "s_spreader": f"{side:.9e}", "t_spreader": "1e-9", "k_spreader": "400.0", "p_spreader": "3.45e6",
        "r_convec": f"{(2 / 3) / (stack.htc * side * side):.9e}", "c_convec": "1e-12",
        "model_secondary": 0, "leakage_used": 0, "package_model_used": 0,
    }
    paths = {k: os.path.join(workdir, f) for k, f in (("config", "hotspot.config"), ("lcf", "stack.lcf"), ("ptrace", "power.ptrace"))}
    open(paths["config"], "w", newline="\n").write("".join(f"\t\t-{k}\t{v}\n" for k, v in cfg.items()))
    open(paths["lcf"], "w", newline="\n").write("\n".join(lcf))
    lines = ["\t".join(names), "\t".join(values)]
    longest = max(len(l) for l in lines)
    if longest + 1 >= LINE_SIZE:
        raise ValueError(f"HotSpot power trace line of {longest} characters exceeds HotSpot's LINE_SIZE ({LINE_SIZE}); "
                         "use a coarser grid or fewer source layers")
    open(paths["ptrace"], "w", newline="\n").write(lines[0] + "\n" + lines[1] + "\n")
    return paths, src
