"""Block floorplans for millimetre-scale dies (G93): rectangles from published die layouts, one power density each.

This is the way HotSpot's own ev6.flp was made (blocks read off a die photo). A floorplan YAML:

    name: zen3_ccd
    size_um: [w, h]
    total_W: 85                    # optional: scale every block's density by one factor so the die sums to this
    background_W_mm2: 0.05         # area no block covers (periphery, fill)
    sources: {isscc22: "AMD, ISSCC 2022 2.7 ...", ...}
    blocks:
      - {name: core0, rect_um: [x, y, w, h], W_mm2: 2.0, kind: logic, source: isscc22, grade: assumption}

`grade` says where each block's position and size come from: primary (the designer's own paper or slides),
secondary (press or teardown reports), assumption (stated here, to sweep). Densities are per block and uniform:
at G93's cells (0.25 to 0.5 mm) the 97 um texture of a routed tile averages out inside one cell, so only the block
layout and its densities reach the solver. `density_from_maps` gives a routed tile's mean density, so a block can
take its density from our own real-activity runs. `power_map` rasterises by exact area overlap, so totals are kept.
"""
from dataclasses import dataclass, field

import numpy as np
import yaml

from .model import _need

GRADES = ("primary", "secondary", "assumption")
KEYS = {"name", "size_um", "total_W", "background_W_mm2", "sources", "blocks"}


@dataclass
class Block:
    name: str
    rect_um: tuple
    W_mm2: float
    kind: str
    source: str
    grade: str


@dataclass
class Floorplan:
    name: str
    size_um: tuple
    blocks: list
    background_W_mm2: float = 0.0
    total_W: float = None
    sources: dict = field(default_factory=dict)

    def validate(self):
        w, h = self.size_um
        for b in self.blocks:
            x, y, bw, bh = b.rect_um
            _need(bw > 0 and bh > 0 and x >= 0 and y >= 0 and x + bw <= w + 1e-6 and y + bh <= h + 1e-6,
                  f"{self.name}: block {b.name} {b.rect_um} is not inside the {w} x {h} um die")
            _need(b.W_mm2 >= 0, f"{self.name}: block {b.name} has negative density")
            _need(b.grade in GRADES, f"{self.name}: block {b.name} grade must be one of {GRADES}")
            _need(b.source in self.sources, f"{self.name}: block {b.name} cites unknown source {b.source!r}")
        for i, a in enumerate(self.blocks):
            for b in self.blocks[i + 1:]:
                _need(_overlap(a.rect_um, b.rect_um) < 1e-6, f"{self.name}: blocks {a.name} and {b.name} overlap")
        names = [b.name for b in self.blocks]
        _need(len(set(names)) == len(names), f"{self.name}: block names must be unique")
        return self

    def raw_W(self):
        """Watts before total_W scaling: blocks plus background on the uncovered area."""
        w, h = self.size_um
        covered = sum(b.rect_um[2] * b.rect_um[3] for b in self.blocks)
        return (sum(b.W_mm2 * b.rect_um[2] * b.rect_um[3] for b in self.blocks)
                + self.background_W_mm2 * (w * h - covered)) * 1e-6

    def power_map(self, grid):
        """(ny, nx) watts per cell over the die, grid = (nx, ny); sums to total_W when it is set."""
        nx, ny = grid
        w, h = self.size_um
        xs, ys = np.linspace(0, w, nx + 1), np.linspace(0, h, ny + 1)
        P = np.full((ny, nx), self.background_W_mm2 * (w / nx) * (h / ny) * 1e-6)
        for b in self.blocks:
            ox = _overlap_1d(xs, b.rect_um[0], b.rect_um[2])         # (nx,) um of the block in each column
            oy = _overlap_1d(ys, b.rect_um[1], b.rect_um[3])
            P += (b.W_mm2 - self.background_W_mm2) * 1e-6 * np.outer(oy, ox)
        return P * (self.total_W / self.raw_W() if self.total_W else 1.0)


def density_from_maps(npz_path, key):
    """Mean power density (W/mm^2) of one window of a routed tile's map (G100 record: die_um and per-window maps)."""
    z = np.load(npz_path)
    x0, y0, x1, y1 = z["die_um"]
    return float(z[key].sum() / ((x1 - x0) * (y1 - y0) * 1e-6))


def load(path):
    d = yaml.safe_load(open(path))
    _need(not set(d) - KEYS, f"{path}: unknown key(s) {sorted(set(d) - KEYS)}")
    blocks = [Block(b["name"], tuple(float(v) for v in b["rect_um"]), float(b["W_mm2"]), b["kind"], b["source"],
                    b["grade"]) for b in d["blocks"]]
    return Floorplan(d["name"], tuple(float(v) for v in d["size_um"]), blocks, float(d.get("background_W_mm2", 0.0)),
                     None if d.get("total_W") is None else float(d["total_W"]), d.get("sources", {})).validate()


def _overlap_1d(edges, start, length):
    return np.clip(np.minimum(edges[1:], start + length) - np.maximum(edges[:-1], start), 0, None)


def _overlap(a, b):
    ox = max(0.0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
    oy = max(0.0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
    return ox * oy
