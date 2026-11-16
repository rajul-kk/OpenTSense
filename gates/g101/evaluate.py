"""Score G101 from runs/<name>/g101_<kit>.json against `registration.md`. Usage: evaluate.py <run dir>"""
import hashlib
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from opentsense import manifest  # noqa: E402

KITS = ["ihp", "asap7", "asap7_lvt"]
INPUTS = ["gates/g101/run.py", "gates/g95/sweep.py", "opentsense/thermal/runaway.py", "opentsense/thermal/electrothermal.py",
          "configs/stacks/g92_ihp.yaml", "configs/stacks/g92b_asap7.yaml"] + [f"gates/g92e/runs/main/{k}/result.json" for k in KITS]
WIDEN, TIE, PRED = 1e-10, 2e-4, 0.25
CLOSE = 1e-12


def window(w):
    c = np.array(w["calls"])                       # rho_eig, lo, hi, iterations, D_min, t_eig, t_power
    r, lo, hi, it, dmin, te, tp = c.T
    sets = w["sets"]
    p = sets["perron"]
    a = bool((hi - lo <= CLOSE * hi).all()      # perron stops at MAX_IT, so an open bracket means it did not close
             and ((r >= lo * (1 - WIDEN)) & (r <= hi * (1 + WIDEN))).all() and ((hi >= 1) == (r >= 1)).all())
    b = all(p["drop"] >= sets[s]["drop"] - TIE for s in ("hot", "leak", "slope"))
    cc = p["drop"] > TIE and abs(p["drop"] - p["pred"]) / p["drop"] <= PRED   # a drop within the bisection's tie is no effect
    return dict(
        valid=bool(len(c) > 0 and (dmin >= 0).all()), a=a, b=bool(b), c=bool(cc), calls=len(c),
        max_rel_gap=float((np.abs(r - np.clip(r, lo, hi)) / r).max()), max_iters=int(it.max()),
        mean_ms_eig=float(te.mean() * 1e3), mean_ms_power=float(tp.mean() * 1e3),
        drops={k: v["drop"] for k, v in sets.items()}, preds={k: v["pred"] for k, v in sets.items()},
        perron_strictly_best=bool(all(p["drop"] > sets[s]["drop"] + TIE for s in ("hot", "leak", "slope"))),
        overlap={s: len(set(p["tiles"]) & set(sets[s]["tiles"])) for s in ("hot", "leak", "slope")},
        peak_T_tile=w["peak_T_tile"], peak_x_tile=w["peak_x_tile"])


def main(d):
    res, missing = {}, []
    for k in KITS:
        f = os.path.join(d, k, f"g101_{k}.json")
        if not os.path.exists(f):
            missing.append(k)
            continue
        g = json.load(open(f))
        res[k] = {w: window(v) for w, v in g["windows"].items()}
        res[k]["R_min"] = g["R_min"]
    rows = [v for k in res for w, v in res[k].items() if w != "R_min"]
    valid = not missing and all(r["valid"] for r in rows) and all(res[k]["R_min"] >= 0 for k in res)
    bars = {x: all(r[x] for r in rows) for x in "abc"}
    verdict = "INCONCLUSIVE" if not valid else ("PASS" if all(bars.values()) else "FAIL")
    out = dict(kits=res, missing=missing, valid=valid, bars=bars, verdict=verdict,
               windows_perron_strictly_best=sum(r["perron_strictly_best"] for r in rows))
    json.dump(out, open(os.path.join(d, "result.json"), "w"), indent=1)
    sha = {p: hashlib.sha256(open(os.path.join(ROOT, p), "rb").read()).hexdigest() for p in INPUTS}
    manifest.write(os.path.join(d, "manifest.json"), {"gate": "G101", "inputs": sha})
    print(verdict, bars, "strictly best", out["windows_perron_strictly_best"], "of", len(rows))


if __name__ == "__main__":
    main(sys.argv[1])
