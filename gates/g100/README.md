# G100: activity windows and power maps on the G99 layouts · Ibex 1,400 ps: PASS · TPU 800 ps: PASS

Registration: `registration.md`. Record: `record/ibex-1400`, `record/tpu-800`. Run: `bash gates/g100/run.sh <ibex 1400|tpu 800>`. G72's
pipeline (Icarus windows, OpenSTA at TT, 32 x 32 tiles) on G99's TT-closed layout at its own clock.

| Bar | Ibex 1,400 ps | TPU 800 ps |
|---|---|---|
| (a) window results | k0-k3 checksums all match | W1, W2 616 of 616 rows; idle W3 none |
| (b) OpenSTA activity annotation | 100% (k0-k4) | 100% (W1-W3) |
| (c) tile maps sum to the design total (bar 1e-3) | worst 6.4e-6 | worst 1.3e-5 |

Reported: power is 60-66% of G72's old layout at its old clock (900 ps), mostly the slower clock; leakage stays
under 0.2% of total at TT. These maps replace G72's for Ibex. Leakage share counts placed (leaf) instances only.

TPU (run 16 Nov, 170 s): power is 22-26% of G72's old layout at its old clock (200 ps), about the 4x slower clock;
leakage 0.5-1.3% of total at TT (highest in idle W3). These maps replace G72's for the TPU.
