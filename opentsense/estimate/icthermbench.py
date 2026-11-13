"""Read-only access to IC-ThermBench S2-S5 steady-state temperature fields (Day333/ThermalBench, arXiv 2608.23977; data
CC BY 4.0), with the benchmark's own index split and a case (package) label per sample.

Only the output temperature is read. A sensor measures temperature, so the inputs, whose spatial channels are stored
transposed relative to the output in the released files (Thermo, notes on IC-ThermBench), are not used here.

Split: the benchmark's, reproduced from its loader (no shuffling): the first 80% is train + val (val = its last 10%),
the rest is test. With contiguous cases this makes the test split a different set of packages:
  level2-4: 15000 samples, Case1-10 x 1500; train = Case1-7 and 300 of Case8, val = the other 1200 of Case8,
            test = Case9-10. The case layout is the dataset README's; it is NOT confirmed from the files (chiplet
            footprints and grids vary within each 1500 block).
  level5:   5000 samples, Case16-20 x 1000 (from manifest.json); train = Case16-18 and 600 of Case19, val = 400 of
            Case19, test = Case20. Confirmed: the grid channels change exactly at the 1000-sample boundaries.
Duplicates: level2 holds byte-identical temperature fields across splits (Thermo note of 4 Nov 2026). `duplicate_mask`
marks every sample whose field also occurs at an earlier split (train before val before test)."""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass

import numpy as np

TRAIN_RATIO, VAL_FRACTION = 0.8, 0.9
LEVELS = ("level2", "level3", "level4", "level5")
DEFAULT_ROOT = os.environ.get("ICTHERMBENCH_ROOT", r"D:\Work\3D-ICE Thermal-modelling\Thermo\data\ic-thermbench\datasets")


def split_indices(total: int) -> dict:
    """The benchmark's split as slices (same arithmetic as its data_loader.split_train_val_test)."""
    tv = max(2, min(int(total * TRAIN_RATIO), total - 1))
    n_train = max(1, min(int(tv * VAL_FRACTION), tv - 1))
    return {"train": slice(0, n_train), "val": slice(n_train, tv), "test": slice(tv, total)}


@dataclass
class Level:
    level: str
    T: np.ndarray            # (N, ny, nx) kelvin, float32
    case: np.ndarray         # (N,) case label, e.g. "Case9"
    split: dict              # name -> slice
    case_source: str         # "manifest" or "README layout (unconfirmed)"


def _cases(folder: str, level: str, N: int):
    man = os.path.join(folder, "manifest.json")
    if os.path.exists(man):
        rows = json.load(open(man))
        if len(rows) != N:
            raise ValueError(f"{man}: {len(rows)} rows for {N} samples")
        return np.array([r["case"] for r in rows]), "manifest"
    if N != 15000:
        raise ValueError(f"{level}: no manifest and {N} samples; the README layout is Case1-10 x 1500")
    return np.repeat([f"Case{k}" for k in range(1, 11)], 1500), "README layout (unconfirmed)"


def load(level: str, root: str = DEFAULT_ROOT, limit: int | None = None) -> Level:
    """Read one level's temperature fields (about 245 MB for level2-4, 82 MB for level5). Opens the files read-only."""
    import h5py                                           # optional dependency (pip install h5py)
    if level not in LEVELS:
        raise ValueError(f"unknown level {level!r}")
    folder = os.path.join(root, f"{level}_steady")
    with h5py.File(os.path.join(folder, "output.mat"), "r") as f:
        d = f["data"]
        if d.ndim != 4 or d.shape[1] != 1:
            raise ValueError(f"expected output (B, 1, Y, X), got {d.shape}")
        N = d.shape[0]
        T = d[: limit or N, 0]                            # (B, Y, X) in file order -> transposed below as upstream does
    T = np.ascontiguousarray(np.swapaxes(T, 1, 2), dtype=np.float32)   # upstream: (B,Z,Y,X) -> (B,X,Y,Z)
    case, src = _cases(folder, level, N)
    return Level(level, T, case[: len(T)], split_indices(N), src)


def field_hashes(T: np.ndarray) -> np.ndarray:
    return np.array([hashlib.sha1(np.ascontiguousarray(t).tobytes()).hexdigest() for t in T])


def duplicate_mask(lv: Level) -> np.ndarray:
    """True for a sample whose field is byte-identical to one in an earlier split, or earlier in its own split."""
    h = field_hashes(lv.T)
    seen, dup = set(), np.zeros(len(h), bool)
    for name in ("train", "val", "test"):
        sl = lv.split[name]
        for i in range(sl.start, min(sl.stop, len(h))):
            dup[i] = h[i] in seen
            seen.add(h[i])
    return dup
