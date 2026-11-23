# G106: Does G102's ranking survive sensors simulated as circuits? (O2, RQ3) · PASS (run 18 Nov 2026)

Registration: `registration.md` (queued as #201 before the run; choices fixed under the student's delegation of
18 Nov). Run: `run.py runs/main 21 30` (chips 1-5 were the dry run, `dry/profiles/`), scored by
`evaluate.py runs/main`. Output `runs/main/` (git-ignored); record: `record/{result,manifest}.json`.

## Verdict: PASS

Validity held: G84's case set rebuilt to its recorded sha256, chips 21-30, salt 106, all six profiles present for
every chip, 10,000 resamples in every run.

| Bar | Needed | Result |
|---|---|---|
| (a) `asap7_ring/regulated`: field model - average, 95% interval below 0, both dies | >= 8 of 10 chips | 10 of 10 on both dies |

## Reported (not gated), chips 21-30

Mean over chips of the field model's RMSE and peak error (mean group median), top / bottom, in K; the average's
RMSE is 3.21 / 2.98 K in every profile; corners drawn per chip (21 to 30); noise the estimators were told (mean over
chips).

| Profile | Chips below the average, top / bottom | Field RMSE | Field peak error | Corners | Told noise |
|---|---|---|---|---|---|
| asap7_ring/regulated (gated) | 10 / 10 | 0.28 / 0.32 | 0.69 / 0.45 | ffffffttss | 0.56 |
| asap7_ring/core_g97 | 10 / 10 | 0.55 / 0.50 | 1.36 / 0.46 | same | 0.90 |
| asap7_ring/core_scaled | 10 / 10 | 1.47 / 1.11 | 3.32 / 0.88 | same | 2.27 |
| ihp_ring/regulated | 9 / 9 | 1.06 / 1.04 | 2.16 / 1.72 | tsfttttsts | 4.11 |
| ihp_dvbe/one_point | 10 / 10 | 1.22 / 1.22 | 2.38 / 2.31 | ttfffffstt | 1.72 |
| ihp_dvbe/two_point | 10 / 10 | 0.51 / 0.57 | 0.95 / 1.22 | same | 0.60 |

Squeeze at the 2 sensors inside the block (test cases): mean 0.47 mV, max 0.78 mV, 2.62 mV after the power-density
scale (3.35 / 3.28 / 3.06 for TPU windows W1-W3, 1.57 on the bottom die).

- **A ring oscillator from our ASAP7 cells, trimmed once, is good enough.** On a regulated supply the field model's
  RMSE is 0.28 / 0.32 K, close to G102's datasheet `ring_osc` class (0.23 / 0.31 K, `../g102/README.md`), and it
  beats the average in every chip. Its error depends on the corner: 0.21 / 0.24 K over the 6 FF chips, 0.10 /
  0.18 K over the 2 TT, 0.65 / 0.70 K over the 2 SS (`runs/main/scores.json`).
- **On the core supply the mean error rises, but not evenly.** At G97's squeeze the RMSE goes from 0.28 / 0.32 to
  0.55 / 0.50 K, and scaled to G84's power density to 1.47 / 1.11 K, still well below the average. Per corner it rises
  on the FF and TT chips and falls on the 2 SS chips (0.65 / 0.70 to 0.16 / 0.35 K). The estimators are also told
  a larger noise (0.90 against 0.56 K), and this run does not separate that from the squeeze itself.
- **The IHP ring's error is set by its corner.** Over chips 21-30 (reported, not gated) it is 0.26 / 0.29 K at TT
  (6 chips), 1.49 / 1.41 K at SS (3) and 4.59 / 4.41 K at FF (1); the one chip where the field model does not beat the average is the
  FF chip (23). The dry run drew FF in 3 of 5 chips, hence its 2 of 5.
- **The dVBE pair needs its second trim point.** It goes from 1.22 K with one trim point to 0.51 / 0.57 K with two
  (the same corner and noise per chip: `run.py` gives the two trims one generator), still above the once-trimmed
  ASAP7 ring's 0.28 / 0.32 K.

**Not claimed.** One stack, steady state, 8 sensors per die on G84's grid; one corner per chip with equal odds
(ASSUMED), no within-die mismatch, no self-heating, no dynamic IR; the squeeze at the 1 mm block is G97's tile squeeze
(with or without the stated scale), not a full-chip PDN.
