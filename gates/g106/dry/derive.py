"""G106 dry run, step 2: the sensor errors a circuit gives, from sweep.json (no SPICE here).

Ring oscillator (per kit): the reader knows the TT, nominal-supply period curve P_tt(T) and trims each chip once at
T_TRIM (one-point ratio trim): it reads T_est = P_tt^-1(P x P_tt(T_TRIM) / P_chip(T_TRIM)), inverting the TT curve by
monotone interpolation in T. Per corner at nominal supply: T_est - T at every swept temperature (the trimmed sensor's
error from the corner's different slope and curvature). Supply, at T_TRIM per corner: droop_K_per_mV, the
reading's rise per mV of supply DROOP (positive = reads hotter), linearised at T_TRIM as
(d ln P / d mV of droop, from the sweep's nearest supply points below and above nominal) / (d ln P_tt / dT at
T_TRIM); the period is close to linear in supply over +-1%, so this is the slope for small squeezes. And the error
the read-back gives for the sweep's nearest droop point (droop_error_K, at droop_mV), through the piecewise-linear
TT inversion.
dVBE pair (IHP): slope at T_TRIM (np.gradient, mV/K); one-point trim, T_est = T_TRIM x dVBE / dVBE_chip(T_TRIM)
(pure PTAT); and a two-point trim at the
sweep's end temperatures (a line through both), whose residual is the curve's own non-linearity.
Constants come from their sources: nominal supplies and the dVBE ratio from estimate.sensor_spice, corners from
power.leak.CORNERS, the supply points from the sweep itself.

Usage (repo root): python gates/g106/dry/derive.py <sweep.json> <out.json>
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")))
from opentsense.estimate import sensor_spice  # noqa: E402
from opentsense.power.leak import CORNERS  # noqa: E402

T_TRIM = 85
K0 = 273.15
KB_Q = 8.617333e-5        # V/K


def ring_read(P_tt, temps, p_chip_trim, P):
    """T_est (C) for periods P of a chip whose period at T_TRIM is p_chip_trim."""
    if np.any(np.diff(P_tt) <= 0):
        raise ValueError("TT period curve is not increasing with temperature")
    x = np.asarray(P, float) * float(np.interp(T_TRIM, temps, P_tt)) / p_chip_trim
    # beyond the swept range, extend the end segments linearly
    lo = temps[0] + (x - P_tt[0]) * (temps[1] - temps[0]) / (P_tt[1] - P_tt[0])
    hi = temps[-1] + (x - P_tt[-1]) * (temps[-1] - temps[-2]) / (P_tt[-1] - P_tt[-2])
    return np.where(x < P_tt[0], lo, np.where(x > P_tt[-1], hi, np.interp(x, P_tt, temps)))


def unit(sw, name):
    if name not in sw["units"]:
        raise ValueError(f"{name} missing from the sweep (a failed deck); rerun sweep.py")
    r = sw["units"][name]["result"]
    return np.array([r[str(t)] for t in sw["temps_C"]])


def main(sweep, out):
    sw = json.load(open(sweep))
    temps = np.array(sw["temps_C"], float)
    i_trim = list(temps).index(T_TRIM)
    down, up = max(s for s in sw["supply"] if s < 1.0), min(s for s in sw["supply"] if s > 1.0)
    res = {"sweep_key": sw["key"], "t_trim_C": T_TRIM, "supply_points": [down, up], "ring": {}, "dvbe": {}}
    for kit, vnom in sensor_spice.NOMINAL_V.items():
        P_tt = unit(sw, f"ring/{kit}/tt/1")
        dlnP_dT = np.gradient(np.log(P_tt), temps)[i_trim]
        k = {"tt_period_s": dict(zip(map(int, temps), P_tt.tolist())),
             "tt_sensitivity_pct_per_K_at_trim": float(dlnP_dT * 100),
             "corner_error_K": {}, "droop_K_per_mV": {}, "droop_error_K": {}, "droop_mV": (1 - down) * vnom * 1000}
        for c in CORNERS:
            P = unit(sw, f"ring/{kit}/{c}/1")
            p_trim = float(P[i_trim])
            err = ring_read(P_tt, temps, p_trim, P) - temps
            k["corner_error_K"][c] = dict(zip(map(int, temps), err.round(3).tolist()))
            p_up, p_down = (float(unit(sw, f"ring/{kit}/{c}/{s:g}")[i_trim]) for s in (up, down))
            dlnP_dmv_droop = (np.log(p_down) - np.log(p_up)) / ((up - down) * vnom * 1000)
            k["droop_K_per_mV"][c] = float(dlnP_dmv_droop / dlnP_dT)
            k["droop_error_K"][c] = float(ring_read(P_tt, temps, p_trim, [p_down])[0] - T_TRIM)
        res["ring"][kit] = k
    for c in CORNERS:
        d = unit(sw, f"dvbe/ihp/{c}")
        one = (T_TRIM + K0) * d / float(np.interp(T_TRIM, temps, d)) - K0
        two = temps[0] + (d - d[0]) * (temps[-1] - temps[0]) / (d[-1] - d[0])
        res["dvbe"][c] = {"dvbe_V": dict(zip(map(int, temps), d.tolist())),
                          "slope_mV_per_K_at_trim": float(np.gradient(d, temps)[i_trim] * 1000),
                          "error_one_point_K": dict(zip(map(int, temps), (one - temps).round(3).tolist())),
                          "error_two_point_K": dict(zip(map(int, temps), (two - temps).round(3).tolist()))}
    res["dvbe"]["ideal_slope_mV_per_K"] = KB_Q * np.log(sensor_spice.DVBE_RATIO) * 1000
    json.dump(res, open(out, "w"), indent=1)
    for kit, k in res["ring"].items():
        worst = {c: max(abs(v) for v in e.values()) for c, e in k["corner_error_K"].items()}
        print(kit, "sens %/K", round(k["tt_sensitivity_pct_per_K_at_trim"], 4),
              "K per mV droop", {c: round(v, 2) for c, v in k["droop_K_per_mV"].items()}, "worst corner err", worst)
    for c in CORNERS:
        print("dvbe", c, "worst one-point", max(map(abs, res["dvbe"][c]["error_one_point_K"].values())),
              "two-point", max(map(abs, res["dvbe"][c]["error_two_point_K"].values())))


if __name__ == "__main__":
    main(*sys.argv[1:3])
