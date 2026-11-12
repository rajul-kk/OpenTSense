"""G84 bars from runs/<id>/{host,image}. Writes runs/<id>/result.json and manifest.json. Usage: evaluate.py <run dir>"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from opentsense import manifest  # noqa: E402

MARGIN, PLUMB = 1e-6, 0.005


def main(run):
    h, i = os.path.join(run, "host"), os.path.join(run, "image")
    rh, ri = json.load(open(os.path.join(h, "result.json"))), json.load(open(os.path.join(i, "result.json")))
    info = json.load(open(os.path.join(h, "cases.json")))
    v = max(info["plumbing_max_dT_K"].values()) <= PLUMB
    dies = rh["case_set"]["dies"]
    a = all(os.path.isfile(os.path.join(h, f)) for f in ("result.json", "per_case.npz", "manifest.json")) and all(
        rh["estimators"][e]["summary"][d]["all"]["peak_err_K"] is not None for e in ("average", "field_model") for d in dies)
    with np.load(os.path.join(h, "cases.npz")) as ch, np.load(os.path.join(i, "cases.npz")) as ci:
        dT = float(np.abs(ch["T"].astype(np.float64) - ci["T"].astype(np.float64)).max())
    with np.load(os.path.join(h, "per_case.npz")) as ph, np.load(os.path.join(i, "per_case.npz")) as pi:
        dm = {k: float(np.nanmax(np.abs(ph[k] - pi[k]))) if np.isfinite(ph[k]).any() else 0.0 for k in ph.files}
    b = dT <= MARGIN and max(dm.values()) <= MARGIN
    c_ = {d: rh["comparisons"]["inverted - average"][d]["rmse_K"] for d in dies}
    c = all(c_[d]["ci95"][0] > 0 for d in dies)
    res = {"gate": "G84", "v": {"ok": v, "plumbing_max_dT_K": info["plumbing_max_dT_K"], "bar_K": PLUMB},
           "a": {"ok": a}, "b": {"ok": b, "case_T_max_abs_diff_K": dT, "per_case_max_abs_diff": dm, "margin": MARGIN},
           "c": {"ok": c, "inverted_minus_average_rmse": c_},
           "case_set": rh["case_set"], "case_set_image_sha256": ri["case_set"]["sha256"],
           "reported": {e: {d: {k: rh["estimators"][e]["summary"][d]["all"][k] for k in ("peak_err_K", "rmse_K", "hotspot_um", "pow_rel")}
                            for d in dies} for e in rh["estimators"]},
           "comparisons": rh["comparisons"]}
    res["verdict"] = "INCONCLUSIVE" if not v else ("PASS" if a and b and c else "FAIL")
    json.dump(res, open(os.path.join(run, "result.json"), "w"), indent=1)
    manifest.write(os.path.join(run, "manifest.json"), {"gate": "G84"})
    print(json.dumps({k: res[k] for k in ("v", "a", "b", "c", "verdict")}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
