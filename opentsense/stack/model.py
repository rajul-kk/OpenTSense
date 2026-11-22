"""Stack description: one YAML file per stack.

Layers are listed from the heat sink downwards (top first), matching 3D-ICE's stack order.
Units in the YAML are SI except lengths, which are in micrometres. Example:

    name: single_die
    size_um: [1000, 1000]
    grid: [32, 32]
    ambient_K: 300
    heat_sink: {htc: 5.0e4}          # W/(m^2 K); side: top (default) or bottom
    materials:
      silicon: {k: 130, cv: 1.63566e6}   # W/(m K), J/(m^3 K)
    layers:
      - {name: spreader, material: copper, thickness_um: 500}
      - {name: tim, material: tim, thickness_um: 25}
      - {name: die0, die: true, material: silicon, thickness_um: 50, source_um: 2}

Optional per layer:
- n_sub: split the layer, or a die's bulk, into n_sub equal sublayers; every solver uses one node per sublayer, so
  thick layers need splitting for hotspots to converge.
- source_side (dies): bottom (the default) or top.
- regions: lateral material map. The layer's `material` fills the layer (for a chiplet layer, the gap: underfill or
  mould); each region {material, rect_um: [x, y, w, h]} overrides it inside its rectangle, through the whole layer
  (for a die: bulk and source). Rectangles must lie on the cell grid and must not overlap. x runs along size_um[0]
  (grid columns), y along size_um[1] (grid rows), from the lower-left corner.

Optional per material (package-level realism, 16 Nov):
- k_lateral: in-plane conductivity when it differs from k, which is then the vertical one (bump, TSV and bond layers;
  `bond_material` computes both). Only 3D-ICE models the difference; HotSpot and PACT are isotropic and use k.
- k_T_exp: k (and k_lateral) scale as (T / 300 K)^-k_T_exp; k is the 300 K value. Silicon is about 1.3. Solvers are
  linear, so `thermal.run.solve_kT` iterates on each layer's temperature.

Optional heat_sink key opposite_htc: a second convective boundary on the face away from the sink (the path down
through package and board), W/(m^2 K). Only 3D-ICE has it; HotSpot and PACT refuse such a stack.

Optional `coldplate` (a ColdPlate, set in code, goal 19): a liquid cold plate of straight microchannels on the sink
face in place of the uniform coefficient (htc is then unused). The coolant enters at ambient_K and warms along the
channels, so the field tilts from inlet to outlet. Only 3D-ICE models channels (its 2-resistor model, 2RM);
HotSpot and PACT refuse such a stack.

Power maps are (ny, nx) arrays over the whole stack footprint, one per die layer. `place` puts a die-local map into
a rectangle of the footprint.
"""
from dataclasses import dataclass, field

import numpy as np
import yaml


@dataclass
class Material:
    k: float   # W/(m K); the vertical value when k_lateral is set
    cv: float  # J/(m^3 K)
    k_lateral: float = None  # W/(m K) in-plane, if it differs from k
    k_T_exp: float = None    # k(T) = k (T / 300 K)^-k_T_exp

    def at(self, T_K):
        """This material at temperature T_K (isotropy and cv unchanged); itself if k does not depend on T."""
        if not self.k_T_exp:
            return self
        f = (T_K / 300.0) ** -self.k_T_exp
        return Material(self.k * f, self.cv, None if self.k_lateral is None else self.k_lateral * f)


@dataclass(frozen=True)
class ColdPlate:
    height_um: float          # channel (and fin) height
    channel_um: float         # channel width
    wall_um: float            # fin width between channels
    wall_material: str        # a material of the stack
    flow_ml_min: float        # coolant flow through the whole plate
    h_top: float              # coolant-to-wall heat transfer coefficients, W/(m^2 K), top and bottom of the channel
    h_bottom: float
    coolant_cv: float = 4.172638e6     # J/(m^3 K), water (3D-ICE's examples)
    cover_um: float = 500.0            # the plate's cover over the channels (wall material, adiabatic top)


def bond_material(k_metal, k_fill, fraction, cv_metal, cv_fill):
    """Effective material of a layer of parallel metal columns (bumps, TSVs, hybrid-bond pads) at area `fraction` in
    a fill: vertical k by the parallel rule, in-plane k by Maxwell-Garnett for aligned cylinders, cv by volume."""
    f = fraction
    k_lat = k_fill * ((1 + f) * k_metal + (1 - f) * k_fill) / ((1 - f) * k_metal + (1 + f) * k_fill)
    return Material(f * k_metal + (1 - f) * k_fill, f * cv_metal + (1 - f) * cv_fill, k_lat)


@dataclass
class Region:
    material: str
    rect_um: tuple  # x, y, w, h


@dataclass
class Layer:
    name: str
    material: str
    thickness_um: float
    die: bool = False
    source_um: float = 0.0  # active (source) sub-layer of a die; counted inside thickness_um
    source_side: str = "bottom"  # which face of the die the source sits on
    n_sub: int = 1  # sublayers for the layer (for a die: for its bulk; the source stays one layer)
    regions: list = field(default_factory=list)

    def __post_init__(self):
        self.regions = [r if isinstance(r, Region) else Region(r["material"], tuple(float(v) for v in r["rect_um"]))
                        for r in self.regions]

    @property
    def bulk_um(self):
        return self.thickness_um - self.source_um


@dataclass
class Stack:
    name: str
    size_um: tuple
    grid: tuple
    ambient_K: float
    htc: float
    materials: dict
    layers: list = field(default_factory=list)
    sink_side: str = "top"
    opposite_htc: float = 0.0  # W/(m^2 K) on the face away from the sink; 0 = adiabatic
    coldplate: ColdPlate = None  # microchannel cold plate on the sink face instead of htc (3D-ICE only)

    @property
    def dies(self):
        return [l for l in self.layers if l.die]

    @property
    def cell_um(self):
        return self.size_um[0] / self.grid[0], self.size_um[1] / self.grid[1]

    def cells(self, rect_um):
        """Rectangle (x, y, w, h) in um -> (j0, j1, i0, i1) cell index ranges (columns j, rows i), exact on the grid."""
        cx, cy = self.cell_um
        x, y, w, h = rect_um
        idx = [x / cx, (x + w) / cx, y / cy, (y + h) / cy]
        r = [int(round(v)) for v in idx]
        if any(abs(a - b) > 1e-6 for a, b in zip(idx, r)):
            raise ValueError(f"rectangle {rect_um} is not on the {cx:g} x {cy:g} um cell grid")
        return tuple(r)

    def material_map(self, layer):
        """(ny, nx) array of material names for a layer."""
        nx, ny = self.grid
        M = np.full((ny, nx), layer.material, dtype=object)
        for r in layer.regions:
            j0, j1, i0, i1 = self.cells(r.rect_um)
            M[i0:i1, j0:j1] = r.material
        return M

    def place(self, P, rect_um):
        """A die-local power map P (rows = y from the rectangle's lower edge) -> (ny, nx) map over the footprint.
        P's shape must equal the rectangle's cell count."""
        j0, j1, i0, i1 = self.cells(rect_um)
        _need(P.shape == (i1 - i0, j1 - j0), f"map {P.shape} does not fit {(i1 - i0, j1 - j0)} cells")
        nx, ny = self.grid
        M = np.zeros((ny, nx))
        M[i0:i1, j0:j1] = P
        return M

    def check_steady(self, power):
        """Every die has a steady (ny, nx) power map in `power` ({die name: W})."""
        nx, ny = self.grid
        for d in self.dies:
            _need(np.shape(power[d.name]) == (ny, nx), f"die {d.name}: steady power map must be {(ny, nx)}, got "
                  f"{np.shape(power[d.name])}; transient (n_slots, ny, nx) maps need 3D-ICE with transient=(step, slot)")

    def check_transient(self, power):
        """Every die has an (n_slots, ny, nx) map, the same n_slots on all; returns n_slots."""
        nx, ny = self.grid
        shapes = {d.name: np.shape(power[d.name]) for d in self.dies}
        _need(all(len(v) == 3 and v[1:] == (ny, nx) for v in shapes.values()),
              f"transient power maps must be (n_slots, {ny}, {nx}), got {shapes}")
        _need(len({v[0] for v in shapes.values()}) == 1, "transient power maps must have the same number of slots on every die")
        return next(iter(shapes.values()))[0]

    def check_one_sink(self, solver):
        """For solvers with one convective face (HotSpot's secondary path is a fixed package model, not this)."""
        _need(self.opposite_htc == 0, f"{solver} has one heat sink; opposite_htc = {self.opposite_htc:g} needs 3D-ICE")
        _need(self.coldplate is None, f"{solver} has no channel model; a cold plate needs 3D-ICE")

    def sublayers(self):
        """(layer, kind, thickness um) for every solver sublayer, starting at the side away from the heat sink.
        kind is "src" for a die's source layer, "bulk" for its bulk sublayers and "" for a passive layer."""
        up = self.sink_side == "top"
        for l in (reversed(self.layers) if up else self.layers):
            if l.die:
                bulk = [("bulk", l.bulk_um / l.n_sub)] * l.n_sub
                src = [("src", l.source_um)]
                parts = src + bulk if (l.source_side == "bottom") == up else bulk + src
            else:
                parts = [("", l.thickness_um / l.n_sub)] * l.n_sub
            for kind, th in parts:
                yield l, kind, th

    def validate(self):
        _need(self.layers, "stack has no layers")
        _need(self.dies, "stack has no die")
        _need(self.sink_side in ("top", "bottom"), "heat_sink side must be top or bottom")
        _need(self.opposite_htc >= 0, "heat_sink opposite_htc must be >= 0")
        if self.coldplate is not None:
            c = self.coldplate
            _need(self.sink_side == "top" and self.opposite_htc == 0, "a cold plate sits on a top sink face, alone")
            _need(c.wall_material in self.materials, f"cold plate: unknown wall material {c.wall_material}")
            # solve_kT re-materialises layer materials only, so a k(T) wall would stay at 300 K
            _need(not self.materials[c.wall_material].k_T_exp, "cold plate: the wall material must not have k(T)")
            _need(not {"coldplate", "coldplate_cover"} & {l.name for l in self.layers},
                  "cold plate: layer names coldplate and coldplate_cover are taken (3D-ICE stack elements)")
            _need(min(c.height_um, c.channel_um, c.wall_um, c.flow_ml_min, c.h_top, c.h_bottom, c.coolant_cv,
                      c.cover_um) > 0,
                  "cold plate: every dimension, the flow, the coefficients and cv must be > 0")
        for name, m in self.materials.items():
            _need(m.k > 0 and m.cv > 0, f"material {name}: k and cv must be > 0")
            _need(m.k_lateral is None or m.k_lateral > 0, f"material {name}: k_lateral must be > 0")
            _need(m.k_T_exp is None or m.k_T_exp >= 0, f"material {name}: k_T_exp must be >= 0")
        nx, ny = self.grid
        for l in self.layers:
            _need(l.material in self.materials, f"layer {l.name}: unknown material {l.material}")
            _need(l.thickness_um > 0, f"layer {l.name}: thickness must be > 0")
            _need(l.n_sub >= 1, f"layer {l.name}: n_sub must be >= 1")
            if l.die:
                _need(0 < l.source_um < l.thickness_um, f"die {l.name}: need 0 < source_um < thickness_um")
                _need(l.source_side in ("bottom", "top"), f"die {l.name}: source_side must be bottom or top")
            seen = np.zeros((ny, nx), bool)
            for r in l.regions:
                _need(r.material in self.materials, f"layer {l.name}: unknown region material {r.material}")
                j0, j1, i0, i1 = self.cells(r.rect_um)
                _need(0 <= j0 < j1 <= nx and 0 <= i0 < i1 <= ny, f"layer {l.name}: region {r.rect_um} outside the footprint")
                _need(not seen[i0:i1, j0:j1].any(), f"layer {l.name}: regions overlap at {r.rect_um}")
                seen[i0:i1, j0:j1] = True
        names = [l.name for l in self.layers]
        _need(len(set(names)) == len(names), "layer names must be unique")
        return self


def _need(ok, msg):
    if not ok:
        raise ValueError(msg)


def _known(where, d, keys):
    """d itself, after refusing any key outside `keys` (a misspelt optional key must not fall back to its default)."""
    _need(not set(d) - keys, f"{where}: unknown key(s) {sorted(set(d) - keys)}")
    return d


def _material(name, v):
    _known(f"material {name}", v, {"k", "cv", "k_lateral", "k_T_exp"})
    opt = lambda key: None if v.get(key) is None else float(v[key])  # noqa: E731
    return Material(float(v["k"]), float(v["cv"]), opt("k_lateral"), opt("k_T_exp"))


def load(path):
    d = yaml.safe_load(open(path))
    hs = d["heat_sink"]
    return Stack(
        name=d["name"],
        size_um=tuple(d["size_um"]),
        grid=tuple(d["grid"]),
        ambient_K=float(d.get("ambient_K", 300.0)),
        htc=float(hs["htc"]),
        materials={m: _material(m, v) for m, v in d["materials"].items()},
        layers=[Layer(**l) for l in d["layers"]],
        sink_side=hs.get("side", "top"),
        opposite_htc=float(_known("heat_sink", hs, {"htc", "side", "opposite_htc"}).get("opposite_htc", 0.0)),
    ).validate()
