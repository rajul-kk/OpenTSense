# G100: activity windows and power maps on the G99 layouts · Ibex 1,400 ps: PASS

Registration: `registration.md`. Record: `record/ibex-1400`. Run: `bash gates/g100/run.sh ibex 1400`. G72's
pipeline (Icarus windows, OpenSTA at TT, 32 x 32 tiles) on G99's TT-closed layout at its own clock.

| Bar | Ibex 1,400 ps |
|---|---|
| (a) window checksums (k0-k3) | all match |
| (b) OpenSTA activity annotation (k0-k4) | 100% |
| (c) tile maps sum to the design total | worst relative difference 6.4e-6 (bar 1e-3) |

Reported: power is 60-66% of G72's old layout at its old clock (900 ps), mostly the slower clock; leakage stays
under 0.2% of total at TT. These maps replace G72's for Ibex. Leakage share counts placed (leaf) instances only.

Not yet: the TPU (windows W1-W3), now that G99 closed for it.
