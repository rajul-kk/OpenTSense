"""Stack -> PACT input (layer CSV, stack config, model config, per-layer floorplan and ptrace CSVs).

PACT lists layers from the bottom up and attaches its heat sink after the LAST layer, so the order is the
reverse of ours. It only accepts a fixed set of material labels, so our materials are mapped onto them;
the label's properties come from our material. Each die becomes a bulk layer plus a source layer.
Grid rows in PACT's output run opposite to 3D-ICE's (see thermal.run.read_pact).
"""
import os

LABELS = ["lump0", "lump1", "Diel", "bcb", "Metal"]  # free labels after Si and Cu

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


def label_map(stack):
    lab, free = {}, iter(LABELS)
    for m in stack.materials:
        lab[m] = "Si" if m == "silicon" else "Cu" if m == "copper" else next(free)
    return lab


def write(stack, power, workdir):
    """power: {die layer name: (ny, nx) array in W}. Returns (args for PACT.py, {die: PACT layer index of its source})."""
    workdir = os.path.abspath(workdir)  # PACT runs from its own source folder, so the layer CSV needs absolute paths
    os.makedirs(workdir, exist_ok=True)
    lab = label_map(stack)
    L, W = stack.size_um[0] * 1e-6, stack.size_um[1] * 1e-6
    nx, ny = stack.grid
    cx, cy = L / nx, W / ny
    # PACT takes a layer's size as its last row's X + Length and needs every layer to match exactly; one block per
    # solid layer can differ from the grid's sum by a rounding error, so solid layers use the same grid of elements
    def grid_flp(label):
        return "UnitName,X,Y,Length (m),Width (m),ConfigFile,Label\n" + "".join(
            f"U_{i}_{j},{j * cx:.9e},{i * cy:.9e},{cx:.9e},{cy:.9e},,{label}\n" for i in range(ny) for j in range(nx))

    cfg = "[DEFAULT]\nlabel = \n\n"
    for m, v in stack.materials.items():
        cfg += f"[{lab[m]}]\nthermalresistivity ((m-k)/w) = {1 / v.k:.6e}\nspecificheatcapacity (j/m^3k) = {v.cv:.4e}\n\n"
    cfg += (f"[Init]\nambient = {stack.ambient_K} K\ntemperature = {stack.ambient_K} K\n\n"
            f"[NoPackage]\nhtc = {stack.htc}\nthickness (m) = 0.000000001\nthermalresistivity ((m-k)/w) = 0.0025\nspecificheatcapacity (j/m^3k) = 3.45e6\n")
    model = MODEL.format(nx=nx, ny=ny)
    for m in stack.materials:
        model += f"\n[{lab[m]}]\nlibrary_name = Solid\nlibrary = Solid.py\ntransient = False\nvirtual_node = bottom_center\nmode = single\n"
    model += "\n[Solid]\nproperties = thermalresistivity ((m-k)/w), specificheatcapacity (j/m^3k)\n"
    # bottom-up: each die is (source, bulk) from the bottom, since its source sits at its lower face
    rows, src_index, li = ["Layer,FloorplanFile,Thickness (m),PtraceFile,LateralHeatFlow"], {}, 0
    for l in reversed(stack.layers):
        parts = [("src", l.source_um), ("bulk", l.thickness_um - l.source_um)] if l.die else [("", l.thickness_um)]
        for kind, th in parts:
            fl = os.path.join(workdir, f"L{li}_flp.csv")
            if kind == "src":
                P = power[l.name]
                open(fl, "w", newline="\n").write(grid_flp(lab[l.material]))
                pt = os.path.join(workdir, f"L{li}_ptrace.csv")
                open(pt, "w", newline="\n").write("UnitName,Power\n" + "".join(f"U_{i}_{j},{P[i, j]:.9e}\n" for i in range(ny) for j in range(nx)))
                rows.append(f"{li},{fl},{th * 1e-6},{pt},True")
                src_index[l.name] = li
            else:
                open(fl, "w", newline="\n").write(grid_flp(lab[l.material]))
                rows.append(f"{li},{fl},{th * 1e-6},,True")
            li += 1
    paths = [os.path.join(workdir, f) for f in ("stack_lcf.csv", "stack.config", "model.config")]
    open(paths[0], "w", newline="\n").write("\n".join(rows) + "\n")
    open(paths[1], "w", newline="\n").write(cfg)
    open(paths[2], "w", newline="\n").write(model)
    return paths, src_index
