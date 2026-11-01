"""OpenSTA per-instance power report + instance locations -> per-tile power maps."""
import re

import numpy as np

NUM = r"[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?"


def read_locations(path):
    L = open(path).read().splitlines()
    box = tuple(float(v) for v in L[0].split(",")[1:])
    pos = {p[0]: (float(p[1]), float(p[2])) for p in (l.split(",") for l in L[1:])}
    return box, pos


def read_power(path):
    """Returns ({instance: (internal, switching, leakage, total) W}, design total W)."""
    txt = open(path, errors="replace").read()
    inst = {}
    for l in txt.splitlines():
        p = l.split()
        if len(p) == 5 and all(re.fullmatch(NUM, v) for v in p[:4]):
            inst[p[4]] = tuple(float(v) for v in p[:4])
    m = re.search(r"^Total\s+(" + NUM + r")\s+(" + NUM + r")\s+(" + NUM + r")\s+(" + NUM + ")", txt, re.M)
    return inst, (float(m.group(4)) if m else None)


def read_annotation(path):
    """(annotated, unannotated) pin counts from OpenSTA's report_activity_annotation, or None without a VCD."""
    txt = open(path, errors="replace").read()
    a = re.search(r"Annotated (\d+) pin", txt)
    u = re.search(r"unannotated\s+(\d+)", txt)
    return (int(a.group(1)), int(u.group(1))) if a and u else None


def tile_map(inst, box, pos, grid, col=3):
    """Sum column `col` of each instance into a (ny, nx) map; row i = y index from the die's lower edge.
    Instances without a location (hierarchical modules, whose children are listed and placed) are skipped and counted."""
    nx, ny = grid
    x0, y0, x1, y1 = box
    M = np.zeros((ny, nx))
    missing = 0
    for n, v in inst.items():
        if n not in pos:
            missing += 1
            continue
        x, y = pos[n]
        i = min(ny - 1, int((y - y0) / (y1 - y0) * ny))
        j = min(nx - 1, int((x - x0) / (x1 - x0) * nx))
        M[i, j] += v[col]
    return M, missing
