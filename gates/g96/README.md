# G96: dynamic power that zero-delay activity misses · Ibex 1,400 ps: valid, glitch share 14.7% (limit 3 stays)

Registration, the two runs and Amendment 1: `registration.md`. Record: `record/ibex-1400` (run 1) and
`record/ibex-1400-a1` (Amendment 1). Run: `bash gates/g96/run.sh ibex 1400`.

| | Run 1 (as registered) | Amendment 1 (made after run 1, from the cause of its failure) |
|---|---|---|
| (a) both simulations reproduce the reference | yes | yes |
| (b) converter: every SDF instance found, every delayed output re-pointed | yes | yes |
| (c) OpenSTA annotation >= 99% | **no** (3,055 pins unannotated) | yes |
| Glitch share of dynamic power | 19.2% (biased high: cell pins before their delay) | **14.7%** |
| Per tile (tiles with >= 0.1% of power) | median 13.1%, max 87% | median 7.9%, max 79% |

Both shares are above the 5% decision threshold, so the decision is the same either way: zero-delay power maps
under-state dynamic power by about 15% on Ibex, and `plan.md` limit 3 stays stated.

Not yet: the TPU window W1. Its SDC has no `set_clock_latency`, so the input time needs a student decision first
(goals decision 10).
