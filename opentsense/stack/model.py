"""Stack description: one YAML file per stack.

Layers are listed from the heat sink downwards (top first), matching 3D-ICE's stack order.
Units in the YAML are SI except lengths, which are in micrometres. Example:

    name: single_die
    size_um: [1000, 1000]
    grid: [32, 32]
    ambient_K: 300
    heat_sink: {htc: 5.0e4}          # W/(m^2 K), on the top face
    materials:
      silicon: {k: 130, cv: 1.63566e6}   # W/(m K), J/(m^3 K)
    layers:
      - {name: spreader, material: copper, thickness_um: 500}
      - {name: tim, material: tim, thickness_um: 25}
      - {name: die0, die: true, material: silicon, thickness_um: 50, source_um: 2}

Optional per layer: n_sub (split the layer, or a die's bulk, into n_sub equal sublayers; both solvers use one
node per sublayer, so thick layers need splitting for hotspots to converge) and, for dies, source_side
(bottom, the default, or top).
"""
from dataclasses import dataclass, field

import yaml


@dataclass
class Material:
    k: float   # W/(m K)
    cv: float  # J/(m^3 K)


@dataclass
class Layer:
    name: str
    material: str
    thickness_um: float
    die: bool = False
    source_um: float = 0.0  # active (source) sub-layer of a die; counted inside thickness_um
    source_side: str = "bottom"  # which face of the die the source sits on
    n_sub: int = 1  # sublayers for the layer (for a die: for its bulk; the source stays one layer)

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

    @property
    def dies(self):
        return [l for l in self.layers if l.die]

    def validate(self):
        assert self.layers, "stack has no layers"
        assert self.dies, "stack has no die"
        for l in self.layers:
            assert l.material in self.materials, f"layer {l.name}: unknown material {l.material}"
            assert l.thickness_um > 0, f"layer {l.name}: thickness must be > 0"
            assert l.n_sub >= 1, f"layer {l.name}: n_sub must be >= 1"
            if l.die:
                assert 0 < l.source_um < l.thickness_um, f"die {l.name}: need 0 < source_um < thickness_um"
                assert l.source_side in ("bottom", "top"), f"die {l.name}: source_side must be bottom or top"
        names = [l.name for l in self.layers]
        assert len(set(names)) == len(names), "layer names must be unique"
        return self


def load(path):
    d = yaml.safe_load(open(path))
    return Stack(
        name=d["name"],
        size_um=tuple(d["size_um"]),
        grid=tuple(d["grid"]),
        ambient_K=float(d.get("ambient_K", 300.0)),
        htc=float(d["heat_sink"]["htc"]),
        materials={m: Material(float(v["k"]), float(v["cv"])) for m, v in d["materials"].items()},
        layers=[Layer(**l) for l in d["layers"]],
    ).validate()
