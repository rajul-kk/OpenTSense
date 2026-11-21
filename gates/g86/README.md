# G86: one failed sensor, and a self-check (RQ3) · FAIL on (c) (run 17 Nov 2026)

Registration: `registration.md` (queued as #117 before the run). Run: `run.py runs/main` (chips 6-15; chips 1-5 were
the dry run), scored by `evaluate.py runs/main`. Output `runs/main/` (git-ignored); record: `record/result.json` and
`record/manifest.json` (the run's manifest, copied as G102's was).

## Verdict: FAIL on bar (c)

Validity held: G84's case set rebuilt to its recorded sha256, the code hashes unchanged from start to end, chips 6-15
and all faults present. The threshold in `scores.json` (z_max 3.4205) equals `fault.threshold(0.01, 16)`, as registered (checked by hand after the run; `evaluate.py` does not check it).

| Bar | Needed | Result |
|---|---|---|
| (a) a known dead sensor: field model below average | >= 95% of 160 pairs, each die | 100% / 100% |
| (b) stuck at ambient, checked: faulty sensor dropped; field model below average | >= 99% of cases; >= 95% of pairs | 100%; 100% / 100% |
| (c) healthy chips: a sensor dropped | <= 1% of cases | **8.5%** (68 of 800) |
| (d) frozen, checked: field model below average | >= 95% of pairs | 100% / 100% |

## Reported (not gated): RMSE in K, mean over the 160 pairs (top / bottom die)

| Fault | Unchecked | Checked | Faulty sensor dropped |
|---|---|---|---|
| none (healthy chips) | 0.23 / 0.31 | | |
| dead, known | 0.24 / 0.32 (worst 0.86) | | |
| stuck at ambient | 1.81 / 1.85 (worst 10.7) | 0.24 / 0.32 (worst 0.86) | 100% |
| frozen | 0.36 / 0.40 (worst 1.79) | 0.27 / 0.34 (worst 0.85) | 35% |
| drift +2 K | 0.23 / 0.33 | 0.24 / 0.34 | 6% |
| drift +1 K | 0.22 / 0.32 | 0.24 / 0.32 | 0.7% |

## Why (c) failed (exploratory, found after the verdict: `dry/chip12.py`)

All 68 false alarms are on one chip (12), all on one sensor (6). Redrawing that chip as `../g102/readings.py` does
gives sensor 6 an offset of +2.69 K, about 2.7 sigma of the ring-oscillator profile's 1.0 K. The check predicts each
sensor from the others with the total error the estimators are told (1.06 K), so an in-specification sensor with a
large fixed offset looks like a fault. The other nine chips raised no false alarm.

## What this means

One failed sensor costs the field model little when it is known (worst 0.86 K, still far below the average's
3 K). The leave-one-out check removes a stuck-at-ambient sensor every time; it catches a frozen sensor in only 35% of
cases, but the ones it misses cost little (checked worst 0.85 K, bar (d) met). Drifts of +1 and +2 K are rarely
caught (0.7%, 6%) and barely move the error. The check, at a threshold set from
the noise model alone, cannot tell a large manufacturing offset from a fault: about one chip in ten here would lose a
healthy sensor. The registration's stated next step applies: calibrate each chip's offsets (or the threshold) on its
cal split before checking. That is a new gate, not a rerun of this one.
