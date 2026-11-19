"""G102 dry run (not scored): chip-to-chip spread of each estimator's RMSE per die and profile, to fix the bars.

Usage (repo root): python gates/g102/dry/floor.py <G84 cases.npz> <out.json>
"""
import json
import os
import sys

import numpy as np

sys.path[:0] = [".", os.path.join("gates", "g102")]
from opentsense.bench.cases import CaseSet  # noqa: E402
from opentsense.bench.score import score  # noqa: E402
import readings  # noqa: E402

EST = ["average", "field_model", "bayes_power", "inverted"]
CHIPS = (1, 2, 3, 4, 5)


def main(cases, out):
    cs = CaseSet.load(cases)
    res = {"case_set_sha256": cs.sha256(), "profiles": {}}
    for prof in readings.sensor.PROFILES:
        rows = []
        for chip in CHIPS:
            r, _ = score(readings.with_sensor(cs, prof, chip), EST, n_boot=2000)
            rows.append({e: {d: r["estimators"][e]["summary"][d]["all"]["rmse_K"] for d in ("top", "bot")} for e in EST}
                        | {"field_minus_avg_ci": {d: r["comparisons"]["field_model - average"][d]["rmse_K"]["ci95"]
                                                  for d in ("top", "bot")}})
        res["profiles"][prof] = rows
        print(prof, json.dumps(rows[0]["field_minus_avg_ci"]), flush=True)
    json.dump(res, open(out, "w"), indent=1)


if __name__ == "__main__":
    main(*sys.argv[1:])
