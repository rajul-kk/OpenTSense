"""Print floor.json as one table per mode: mean RMSE over chips and sensors, the worst sensor, and how many
(chip, sensor) pairs keep the field model's interval below the average's (G102's bar (a)), per die.

Usage: python gates/g86/dry/summarise.py gates/g86/dry/floor.json
"""
import json
import sys

import numpy as np


def main(path):
    r = json.load(open(path))
    chips = list(r["chips"].values())
    print("z_max", round(r["z_max"], 3), "false alarms", [c["false_alarm_share"] for c in chips])
    for mode in ("healthy", "healthy_checked"):
        for d in ("top", "bot"):
            v = [c[mode][d]["mean_group_median_K"] for c in chips]
            below = sum(c[mode][d]["vs_average_ci95"][1] < 0 for c in chips)
            print(f"{mode:16s} {d}: mean {np.mean(v):.3f} K, max {max(v):.3f} K, CI<0 in {below}/{len(chips)} chips")
    for mode in ("dead", "stuck", "checked"):
        for d in ("top", "bot"):
            rows = [(s[mode][d]["mean_group_median_K"], s[mode][d]["vs_average_ci95"][1] < 0)
                    for c in chips for s in c["sensors"].values()]
            v = np.array([x for x, _ in rows])
            print(f"{mode:16s} {d}: mean {v.mean():.3f} K, worst {v.max():.3f} K, "
                  f"CI<0 in {sum(b for _, b in rows)}/{len(rows)} (chip, sensor) pairs")
    det = [s["detected_share"] for c in chips for s in c["sensors"].values()]
    print("detected share: min", min(det), "mean", round(float(np.mean(det)), 4))


if __name__ == "__main__":
    main(sys.argv[1])
