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

Power maps are (ny, nx) arrays over the whole stack footprint, one per die layer. `place` puts a die-local map into
a rectangle of the footprint.
"""
from dataclasses import dataclass, field

import numpy as np
import yaml


@dataclass
class Material:
    k: float   # W/(m K)
    cv: float  # J/(m^3 K)


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


def load(path):
    d = yaml.safe_load(open(path))
    hs = d["heat_sink"]
    return Stack(
        name=d["name"],
        size_um=tuple(d["size_um"]),
        grid=tuple(d["grid"]),
        ambient_K=float(d.get("ambient_K", 300.0)),
        htc=float(hs["htc"]),
        materials={m: Material(float(v["k"]), float(v["cv"])) for m, v in d["materials"].items()},
        layers=[Layer(**l) for l in d["layers"]],
        sink_side=hs.get("side", "top"),
    ).validate()
