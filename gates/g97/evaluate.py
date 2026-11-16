"""Score G97 from runs/<name>/<window>/ against registration.md (Amendments 1 and 2). Usage: evaluate.py <run dir>"""
import hashlib
import json
import os
import re
import sys

import numpy as np
from scipy.stats import spearmanr

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from opentsense import manifest  # noqa: E402
from opentsense.power import maps  # noqa: E402

WINDOWS = ["k0", "k1", "k2", "k3", "k4"]
NETS, SOURCES = ["VDD", "VSS"], ["FULL", "BUMPS"]
VDD, GRID = 0.7, (32, 32)                      # VDD is checked against PDNSim's "Supply voltage" in every log
TILE_MIN_FRAC, SQUEEZE_FRAC = 0.001, 0.025      # decision: squeeze >= 2.5% of VDD in a tile with >= 0.1% of power
G100_REC = "gates/g100/record/ibex-1400/result.json"
G100_RUN = "gates/g100/runs/ibex-1400"
LAYOUT = os.path.join(ROOT, "..", "..", "_build", "g99", "asap7-ibex-1400", "results", "asap7", "ibex", "base")
INPUTS = ["gates/g97/registration.md", "gates/g97/ir.tcl", "gates/g97/run.sh", "gates/g97/evaluate.py",
          "gates/g96/dry/load_routed.tcl", "opentsense/power/maps.py", G100_REC,
          f"{G100_RUN}/maps.npz", f"{G100_RUN}/power/ibex_loc.csv"]


def voltages(path, worst):
    """{instance: its worst terminal voltage} (min for VDD, max for VSS)."""
    v = {}
    with open(path) as fh:
        next(fh)
        for line in fh:
            inst, _, _, _, _, volt = line.rstrip().split(",")
            x = float(volt)
            v[inst] = worst(v[inst], x) if inst in v else x
    return v


def analyses(log):
    """{(net, source): (total power W, supply V)} from each ANALYZE block, each read only up to the next marker."""
    out = {}
    for net, src, body in re.findall(r"^ANALYZE (\w+) (\w+):\n(.*?)(?=^ANALYZE |^CHECK |\Z)", log, re.S | re.M):
        p = re.search(r"Total power\s*:\s*(\S+) W", body)
        v = re.search(r"Supply voltage\s*:\s*(\S+) V", body)
        out[(net, src)] = (float(p.group(1)) if p else None, float(v.group(1)) if v else None)
    return out


def tile_stats(values, box, pos):
    """Per-tile mean and max of an instance quantity on G100's grid, and the instance count per tile."""
    s, n, m = (np.zeros((GRID[1], GRID[0])) for _ in range(3))
    for inst, q in values.items():
        ij = maps.tile_index(pos[inst], box, GRID)
        s[ij] += q
        n[ij] += 1
        m[ij] = max(m[ij], q)
    return np.divide(s, n, out=np.zeros_like(s), where=n > 0), m, n


def window(d, g100_total, box, pos, power_map):
    log = open(os.path.join(d, "ir.log")).read()
    sta_total = maps.read_power(os.path.join(d, "ir.log"))[1]
    blocks = analyses(log)
    checks = all(re.search(rf"^CHECK {n}:\n\[INFO PSM-0040\] All shapes on net {n} are connected", log, re.M) for n in NETS)
    errors = [f for f in os.listdir(d) if f.startswith(("check_", "err_"))]
    big = power_map >= TILE_MIN_FRAC * power_map.sum()
    out, tiles = {"sta_total_W": sta_total, "g100_total_W": g100_total,
                  "psm": {f"{n} {s}": {"total_W": p, "supply_V": v} for (n, s), (p, v) in blocks.items()}}, {}
    for src in SOURCES:
        vdd = voltages(os.path.join(d, f"v_VDD_{src}.csv"), min)
        vss = voltages(os.path.join(d, f"v_VSS_{src}.csv"), max)
        placed = [i for i in pos if i in vdd and i in vss]
        drop = {i: VDD - vdd[i] for i in placed}
        rise = {i: vss[i] for i in placed}
        squeeze = {i: drop[i] + rise[i] for i in placed}
        mean_t, max_t, n_t = tile_stats(squeeze, box, pos)
        has = n_t > 0
        worst = {"vdd_drop": max(drop.values()), "vss_rise": max(rise.values()), "squeeze": max(squeeze.values()),
                 "tile_squeeze": float(max_t[big].max())}
        out[src] = {**{f"worst_{k}_mV": 1e3 * v for k, v in worst.items()},
                    **{f"worst_{k}_share_of_vdd": v / VDD for k, v in worst.items()},
                    "mean_squeeze_mV": 1e3 * float(np.mean(list(squeeze.values()))),
                    "spearman_squeeze_vs_power": float(spearmanr(mean_t[has], power_map[has])[0]),
                    "covered": len(placed) == len(pos)}
        tiles[src] = (mean_t, max_t, vdd)
    want = {(n, s) for n in NETS for s in SOURCES}
    out["valid"] = {"V1_grid": bool(checks) and not errors,
                    "V2_power": sta_total is not None and abs(sta_total - g100_total) <= 1e-6 * g100_total,
                    "V3_psm_power": set(blocks) == want and all(
                        p is not None and abs(p - sta_total) <= 0.01 * sta_total for p, _ in blocks.values()),
                    "V4_covered": all(out[s]["covered"] for s in SOURCES),
                    "supply_is_vdd": all(v is not None and abs(v - (VDD if n == "VDD" else 0.0)) < 1e-9
                                         for (n, _), (_, v) in blocks.items()) and set(blocks) == want}
    out["matters"] = out["FULL"]["worst_tile_squeeze_share_of_vdd"] >= SQUEEZE_FRAC
    return out, tiles


def main(run):
    g100 = json.load(open(os.path.join(ROOT, G100_REC)))
    box, pos = maps.read_locations(os.path.join(ROOT, G100_RUN, "power", "ibex_loc.csv"))
    pmaps = np.load(os.path.join(ROOT, G100_RUN, "maps.npz"))
    res, fields, vdd_maps = {}, {}, []
    for w in WINDOWS:
        res[w], tiles = window(os.path.join(run, w), g100[w]["total_W"], box, pos, pmaps[w])
        for src, (mean_t, max_t, vdd) in tiles.items():
            fields[f"{w}_{src}_mean"], fields[f"{w}_{src}_max"] = mean_t, max_t
        vdd_maps.append(tuple(sorted(tiles["FULL"][2].items())))
    distinct = len(set(vdd_maps)) > 1                     # V3: the windows' activity reached PDNSim
    valid = distinct and all(all(res[w]["valid"].values()) for w in WINDOWS)
    worst = max(res[w]["FULL"]["worst_tile_squeeze_mV"] for w in WINDOWS)
    out = {"windows": res, "maps_differ_across_windows": distinct, "valid": valid, "worst_tile_squeeze_mV": worst,
           "worst_tile_squeeze_share_of_vdd": worst / 1e3 / VDD, "threshold_mV": 1e3 * SQUEEZE_FRAC * VDD,
           "decision": None if not valid else ("IR matters to the power maps" if any(res[w]["matters"] for w in WINDOWS)
                                               else "nominal-VDD power maps stand; limit stated")}
    json.dump(out, open(os.path.join(run, "result.json"), "w"), indent=1)
    np.savez_compressed(os.path.join(run, "maps.npz"), die_um=box, **fields)
    sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()  # noqa: E731
    inputs = {p: sha(os.path.join(ROOT, p)) for p in INPUTS}
    inputs.update({f"layout/6_final.{e}": sha(os.path.join(LAYOUT, f"6_final.{e}")) for e in ("odb", "sdc", "spef")})
    inputs.update({f"vcd/{w}.vcd": sha(os.path.join(ROOT, G100_RUN, "sim", "ibex", f"{w}.vcd")) for w in WINDOWS})
    manifest.write(os.path.join(run, "manifest.json"), {"gate": "G97", "inputs_sha256": inputs})
    print("valid" if valid else "INVALID", out["decision"], f"worst tile squeeze {worst:.2f} mV")


if __name__ == "__main__":
    main(sys.argv[1])
