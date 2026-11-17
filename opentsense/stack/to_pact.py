"""Stack -> PACT input (layer CSV, stack config, model config, per-layer floorplan and ptrace CSVs).

PACT attaches its heat sink after the LAST layer it is given. With the sink on top that is the reverse of our
top-first order; with the sink at the bottom it is our order. PACT (as released) only accepts a fixed set of
material labels, so our materials are mapped onto them, the label's properties coming from our material. Beyond
those labels a material keeps its own name, which needs the image's PACT patch (pact-labels.patch: any label with a
section in the stack config is an isotropic solid). Each die becomes a bulk layer plus a source layer. Layers with
regions get one label per grid cell.
PACT numbers its grid rows from the opposite edge to ours; `rows` and `cell` are the only places that know it.
"""
import os

import numpy as np

LABELS = ["lump0", "lump1", "Diel", "bcb", "Metal", "Metal7_8"]  # free labels after Si and Cu
SINK_FILM_M, SINK_FILM_CV = 1e-9, 3.45e6  # PACT's NoPackage sink: a copper film that carries the htc; a node layer too

MODEL = """[DEFAULT]
label =

[Path]
home = ./../
library = %(home)slib/
flp = %(home)sflp_files/
ptrace = %(home)sptrace_files/

[Simulation]
steady_state = True
steady_state_solver = Solver
transient = False
temperature_dependent = False
convergence = 0.1
layer = 1
temperature_dependent_library = TemperatureDependent.py
number_of_core = 1
init_file = False

[Solver]
name = SuperLU
wrapper = SuperLUSolver.py

[Grid]
type = Uniform
granularity = Grid
rows = {ny}
cols = {nx}
grid_mode = avg

[VirtualNodes]
center_center = 0.5
bottom_center = 1

[NoPackage]
LateralHeatFlow = True
VerticalHeatFlow = False
library_name = NoPackage_sec
library = Solid.py
virtual_node = bottom_center
transient = False
mode = single

[NoPackage_sec]
properties = htc, thickness (m), thermalresistivity ((m-k)/w), specificheatcapacity (j/m^3k)
"""


def rows(M):
    """A (..., ny, nx) map in our row order <-> PACT's: PACT row r is our row ny-1-r (the map is its own inverse;
    point-source check in exploratory gate G47)."""
    return M[..., ::-1, :]


def cell(stack, layer, i, j):
    """PACT's flat node index of our cell (row i, column j) on PACT layer `layer`; i and j may be arrays."""
    nx, ny = stack.grid
    return layer * nx * ny + (ny - 1 - np.asarray(i)) * nx + np.asarray(j)


def rhs(stack, power, src):
    """Power pattern {die: (ny, nx) W} as a right-hand side in PACT's (layer, row, col) node order, up to the last
    source layer (PACT's own b adds the ambient term on the layer next to the sink)."""
    nx, ny = stack.grid
    b = np.zeros((max(src.values()) + 1, ny, nx))
    for d, P in power.items():
        b[src[d]] = rows(P)
    return b.ravel()


def capacity(stack):
    """Heat capacity of every PACT node (J/K) in PACT's order, as PACT's Solid.py sets it: cv x cell volume; the
    sink film is PACT's last node layer."""
    nx, ny = stack.grid
    cell_m2 = stack.size_um[0] * stack.size_um[1] * 1e-12 / (nx * ny)
    cv = {m: v.cv for m, v in stack.materials.items()}
    return np.concatenate([rows(np.vectorize(cv.get, otypes=[float])(stack.material_map(l))).ravel() * cell_m2 * th * 1e-6
                           for l, _, th in stack.sublayers()] + [np.full(nx * ny, SINK_FILM_CV * SINK_FILM_M * cell_m2)])


def label_map(stack):
    lab, free = {}, iter(LABELS)
    for m in stack.materials:
        lab[m] = "Si" if m == "silicon" else "Cu" if m == "copper" else next(free, None) or "M_" + "".join(c if c.isalnum() else "_" for c in m)
    return lab


def write(stack, power, workdir):
    """power: {die layer name: (ny, nx) array in W}. Returns (args for PACT.py, {die: PACT layer index of its source})."""
    stack.check_steady(power)
    stack.check_one_sink("PACT")
    workdir = os.path.abspath(workdir)  # PACT runs from its own source folder, so the layer CSV needs absolute paths
    os.makedirs(workdir, exist_ok=True)
    lab = label_map(stack)
    L, W = stack.size_um[0] * 1e-6, stack.size_um[1] * 1e-6
    nx, ny = stack.grid
    cx, cy = L / nx, W / ny
    # PACT takes a layer's size as its last row's X + Length and needs every layer to match exactly; one block per
    # solid layer can differ from the grid's sum by a rounding error, so solid layers use the same grid of elements
    def grid_flp(layer):
        M = stack.material_map(layer)
        return "UnitName,X,Y,Length (m),Width (m),ConfigFile,Label\n" + "".join(
            f"U_{i}_{j},{j * cx:.9e},{i * cy:.9e},{cx:.9e},{cy:.9e},,{lab[M[i, j]]}\n" for i in range(ny) for j in range(nx))

    cfg = "[DEFAULT]\nlabel = \n\n"
    for m, v in stack.materials.items():
        cfg += f"[{lab[m]}]\nthermalresistivity ((m-k)/w) = {1 / v.k:.6e}\nspecificheatcapacity (j/m^3k) = {v.cv:.4e}\n\n"
    cfg += (f"[Init]\nambient = {stack.ambient_K} K\ntemperature = {stack.ambient_K} K\n\n"
            f"[NoPackage]\nhtc = {stack.htc}\nthickness (m) = {SINK_FILM_M:.0e}\nthermalresistivity ((m-k)/w) = 0.0025\n"
            f"specificheatcapacity (j/m^3k) = {SINK_FILM_CV:.2e}\n")
    model = MODEL.format(nx=nx, ny=ny)
    for m in stack.materials:
        model += f"\n[{lab[m]}]\nlibrary_name = Solid\nlibrary = Solid.py\ntransient = False\nvirtual_node = bottom_center\nmode = single\n"
    model += "\n[Solid]\nproperties = thermalresistivity ((m-k)/w), specificheatcapacity (j/m^3k)\n"
    lcf, src_index, li = ["Layer,FloorplanFile,Thickness (m),PtraceFile,LateralHeatFlow"], {}, 0
    for l, kind, th in stack.sublayers():
        fl = os.path.join(workdir, f"L{li}_flp.csv")
        if kind == "src":
            P = power[l.name]
            open(fl, "w", newline="\n").write(grid_flp(l))
            pt = os.path.join(workdir, f"L{li}_ptrace.csv")
            open(pt, "w", newline="\n").write("UnitName,Power\n" + "".join(f"U_{i}_{j},{P[i, j]:.9e}\n" for i in range(ny) for j in range(nx)))
            lcf.append(f"{li},{fl},{th * 1e-6},{pt},True")
            src_index[l.name] = li
        else:
            open(fl, "w", newline="\n").write(grid_flp(l))
            lcf.append(f"{li},{fl},{th * 1e-6},,True")
        li += 1
    paths = [os.path.join(workdir, f) for f in ("stack_lcf.csv", "stack.config", "model.config")]
    open(paths[0], "w", newline="\n").write("\n".join(lcf) + "\n")
    open(paths[1], "w", newline="\n").write(cfg)
    open(paths[2], "w", newline="\n").write(model)
    return paths, src_index
