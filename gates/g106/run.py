"""G106: G102's harness with sensors simulated as circuits (registration.md; `dry/derive.json` gives the profiles).

Profiles (estimate.sensor_circuit, readout step 0.25 K and noise 0.1 K as G102's ring_osc, one corner per chip):
  asap7_ring/regulated      the ASAP7 ring after its one-point trim, no supply term            (gated)
  asap7_ring/core_g97       on the core supply: G97's tile squeeze at the sensor                (reported)
  asap7_ring/core_scaled    the same squeeze times G84's block power density over G97's        (reported)
  ihp_ring/regulated        the IHP ring (a poor thermometer at 1.2 V)                          (reported)
  ihp_dvbe/one_point        the IHP dVBE pair, one-point trim                                   (reported)
  ihp_dvbe/two_point        the same, two-point trim                                            (reported)
Cases of one sensor share its generator (asap7_ring's three; the dVBE pair's two trims), so they see the same corner
and read noise per chip and pair by chip.
Squeeze at a sensor (mV): inside G71's active block (cells 20-39 of each die), the G97 map resampled onto the block
by area mean: on the top (TPU) die the case's own TPU window W1-W3 (`gates/g97/runs/tpu/maps.npz`, FULL source,
tile mean), on the bottom (CPU) die the mean of Ibex's windows k0-k4 (`gates/g97/runs/main/maps.npz`); outside the
block 0 (the dark area draws little current). The scaled case multiplies the squeeze by G84's block power density
over G97's, per window on the top die: 6.936 W/mm^2 x the window's power relative to W1 (G72's maps, as G84's
make_cases) over G97's TPU power for that window (W1 19.66, W2 17.56, W3 12.90 mW, G97 README) on its 97.448 x 97.448 um
die; on the bottom die 1.0719 W/mm^2 over Ibex's mean power over k0-k4 on its 76.726 x 76.726 um die. Squeeze taken
as proportional to local power density for the same grid per area (ASSUMED).
Scored as G102 (average and field model, test split, group bootstrap, 10,000 resamples); the field model is fitted
once on the train fields.

Usage (repo root, host): python gates/g106/run.py <out dir> <first chip> <last chip>
  gated: runs/main 21 30; dry: dry/profiles 1 5
"""
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from opentsense import manifest  # noqa: E402
from opentsense.bench import readings  # noqa: E402
from opentsense.bench.cases import CaseSet  # noqa: E402
from opentsense.bench.estimators import FieldModel  # noqa: E402
from opentsense.bench.score import score  # noqa: E402
from opentsense.estimate.field_model import GaussianField  # noqa: E402
from opentsense.estimate.sensor_circuit import CircuitProfile  # noqa: E402

SALT = 106
G84_SHA = "f5941ad74a0d62f256c052607607be24985eaaa3c43fffe3fa10514a677f6e7c"
DERIVE = "gates/g106/dry/derive.json"
TPU_MAPS, IBEX_MAPS, BLOCK = "gates/g97/runs/tpu/maps.npz", "gates/g97/runs/main/maps.npz", "gates/g71/inputs/maps.npz"
G72_MAPS = "gates/g72/runs/main/maps.npz"
TPU_W_PER_MM2 = 6.9360          # G84's TPU block (make_cases.TPU_BLOCK_W over its 1 mm^2)
CPU_W_PER_MM2 = 1.0719
G97_TPU_W = {"W1": 19.66e-3, "W2": 17.56e-3, "W3": 12.90e-3}            # G97 README, TPU part
G97_IBEX_W = {"k0": 4.45e-3, "k1": 4.82e-3, "k2": 4.70e-3, "k3": 4.39e-3, "k4": 1.69e-3}


def files(cs):
    return sorted({"gates/g106/run.py", "gates/g106/evaluate.py", "gates/g106/registration.md", DERIVE, TPU_MAPS,
                   IBEX_MAPS, BLOCK, G72_MAPS, "gates/g84/make_cases.py",
                   os.path.relpath(os.path.join(readings.STACKS, f"{cs.stack_id}.yaml"), ROOT).replace(os.sep, "/")})


def inputs(cs):
    mods = {os.path.relpath(m.__file__, ROOT).replace(os.sep, "/") for m in list(sys.modules.values())
            if getattr(m, "__file__", None) and os.path.abspath(m.__file__).startswith(os.path.join(ROOT, "opentsense"))}
    return {p: manifest.file_sha256(os.path.join(ROOT, p)) if os.path.exists(os.path.join(ROOT, p)) else None
            for p in sorted(mods | set(files(cs)))}            # None: not written yet (the registration, in the dry run)


def block_mean(M, n):
    """Area-mean resample of a square (k, k) map to (n, n)."""
    k = M.shape[0]
    return np.kron(M, np.ones((n, n))).reshape(n, k, n, k).mean((1, 3))


def squeeze_mV(cs):
    """(N, m) squeeze at each sensor in each case (mV), the (N, m) power-density scale of the scaled case, the scale
    per die and window, and which sensors lie inside the block."""
    act = np.load(os.path.join(ROOT, BLOCK))["act3"].astype(bool)
    (r0, c0), (r1, c1) = np.argwhere(act).min(0), np.argwhere(act).max(0) + 1
    if r1 - r0 != c1 - c0:
        raise ValueError("the active block is not square")
    n = r1 - r0
    tz, iz = np.load(os.path.join(ROOT, TPU_MAPS)), np.load(os.path.join(ROOT, IBEX_MAPS))
    die_map = {"top": {w: block_mean(tz[f"{w}_FULL_mean"], n) * 1e3 for w in G97_TPU_W},
               "bot": block_mean(np.mean([iz[f"{k}_FULL_mean"] for k in G97_IBEX_W], 0), n) * 1e3}
    s = cs.sensors
    inside = act[s[:, 1], s[:, 2]]
    out, scale = np.zeros((cs.N, len(s))), np.ones((cs.N, len(s)))
    g72 = np.load(os.path.join(ROOT, G72_MAPS))
    rel = {w: float(g72[f"tpu_{w}"].sum() / g72["tpu_W1"].sum()) for w in G97_TPU_W}
    tpu_um2, ibex_um2 = (float((b[2] - b[0]) * (b[3] - b[1])) for b in (tz["die_um"], iz["die_um"]))
    per = {"top": {w: TPU_W_PER_MM2 * rel[w] / (G97_TPU_W[w] / tpu_um2 * 1e6) for w in G97_TPU_W},
           "bot": CPU_W_PER_MM2 / (np.mean(list(G97_IBEX_W.values())) / ibex_um2 * 1e6)}
    work = [str(w) for w in cs.a["tpu_workload"]]
    for j, (d, r, c) in enumerate(s):
        if not inside[j]:
            continue
        die = str(cs.dies[d])
        if die == "top":
            out[:, j] = [die_map["top"][w][r - r0, c - c0] for w in work]
            scale[:, j] = [per["top"][w] for w in work]
        else:
            out[:, j] = die_map["bot"][r - r0, c - c0]
            scale[:, j] = per["bot"]
    return out, scale, per, inside


def profiles():
    d = json.load(open(os.path.join(ROOT, DERIVE)))
    return {"asap7_ring": CircuitProfile.ring(d, "asap7"), "ihp_ring": CircuitProfile.ring(d, "ihp"),
            "ihp_dvbe_1pt": CircuitProfile.dvbe(d, "one_point"), "ihp_dvbe_2pt": CircuitProfile.dvbe(d, "two_point")}


def main(out, first, last):
    chips = list(range(int(first), int(last) + 1))
    os.makedirs(out, exist_ok=True)
    cases = os.path.join(out, "cases.npz")
    if not os.path.exists(cases):
        tmp = os.path.abspath(os.path.join(out, "cases.tmp.npz"))
        subprocess.run([sys.executable, os.path.join(ROOT, "gates", "g84", "make_cases.py"), tmp], check=True, cwd=ROOT)
        os.replace(tmp, cases)
        os.replace(tmp[:-4] + ".json", os.path.join(out, "cases.json"))
    cs = CaseSet.load(cases)
    if cs.sha256() != G84_SHA:
        manifest.write_json({"case_set_sha256": cs.sha256(), "runs": {}}, os.path.join(out, "scores.json"))
        raise SystemExit(f"case set {cs.sha256()} is not G84's {G84_SHA}: INCONCLUSIVE before scoring")
    hashes = inputs(cs)
    manifest.write(os.path.join(out, "manifest.json"), {"gate": "G106", "inputs_sha256": hashes})
    sq, scale, per, inside = squeeze_mV(cs)
    tr = cs.idx("train")
    gf = GaussianField(energy=FieldModel().energy).fit(cs.T[tr].reshape(len(tr), -1))
    prof = profiles()
    cases_run = {"asap7_ring/regulated": ("asap7_ring", "asap7_ring", None),            # (generator, profile, squeeze)
                 "asap7_ring/core_g97": ("asap7_ring", "asap7_ring", sq),
                 "asap7_ring/core_scaled": ("asap7_ring", "asap7_ring", sq * scale),
                 "ihp_ring/regulated": ("ihp_ring", "ihp_ring", None),
                 "ihp_dvbe/one_point": ("ihp_dvbe", "ihp_dvbe_1pt", None),
                 "ihp_dvbe/two_point": ("ihp_dvbe", "ihp_dvbe_2pt", None)}
    te = cs.idx("test")
    res = {"case_set_sha256": cs.sha256(), "chips": chips, "salt": SALT,
           "squeeze_mV": {"sensors_inside_block": int(inside.sum()), "test_mean": float(sq[te].mean()),
                          "test_mean_inside": float(sq[te][:, inside].mean()),
                          "test_max": float(sq[te].max()), "test_max_scaled": float((sq * scale)[te].max())},
           "density_scale": per, "runs": {}}
    for name, (gen, pname, s) in cases_run.items():
        for chip in chips:
            c, corner = readings.read_circuit(cs, gen, prof[pname], chip, SALT, s)
            r, _ = score(c, ["average", "field_model"], estimators={"field_model": FieldModel(gf=gf)})
            res["runs"][f"{name}/{chip}"] = {"corner": corner, "noise_K": float(c.noise_K),
                                             "n_boot": r["comparisons"]["field_model - average"]["top"]["rmse_K"]["n_boot"],
                                             "field_model": r["estimators"]["field_model"]["summary"],
                                             "average": r["estimators"]["average"]["summary"],
                                             "vs_average": r["comparisons"]["field_model - average"]}
        print(name, "done", flush=True)
    if inputs(cs) != hashes:
        raise SystemExit("code changed during the run; the scores are not recorded")
    manifest.write_json(res, os.path.join(out, "scores.json"))


if __name__ == "__main__":
    main(*sys.argv[1:4])
