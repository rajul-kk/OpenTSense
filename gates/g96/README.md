# G96: dynamic power that zero-delay activity misses · valid on both designs: Ibex 14.7%, TPU 19.1% (limit 3 stays)

Registration, the runs and Amendments 1-3: `registration.md`. Record: `record/ibex-1400` (run 1),
`record/ibex-1400-a1` (Amendment 1), `record/tpu-800`. Run: `bash gates/g96/run.sh ibex 1400`, `... tpu 800`.

| | Run 1 (as registered) | Amendment 1 (made after run 1, from the cause of its failure) |
|---|---|---|
| (a) both simulations reproduce the reference | yes | yes |
| (b) converter: every SDF instance found, every delayed output re-pointed | yes | yes |
| (c) OpenSTA annotation >= 99% | **no** (3,055 pins unannotated) | yes |
| Glitch share of dynamic power | 19.2% (biased high: cell pins before their delay) | **14.7%** |
| Per tile (tiles with >= 0.1% of power) | median 13.1%, max 87% | median 7.9%, max 79% |

Both shares are above the 5% decision threshold, so the decision is the same either way: zero-delay power maps
under-state dynamic power by about 15% on Ibex, and `plan.md` limit 3 stays stated.

## TPU W1, 800 ps (16 Nov 2026, with Amendments 1 and 3)

| | TPU W1 |
|---|---|
| (a) both simulations reproduce the reference (616 rows each) | yes |
| (b) converter: every SDF instance found (0 missing), outputs cut = outputs re-pointed (55,161) | yes |
| (c) OpenSTA annotation >= 99% | yes (100% in both runs) |
| Dynamic power, zero-delay / delay-aware | 19.53 / 24.15 mW |
| Glitch share of dynamic power | **19.1%** (before the view: 23.1%) |
| Per tile (442 tiles with >= 0.1% of power) | median 9.2%, max 73% |
| Toggle ratio, delay-aware / zero-delay simulation | 3.33 |
| Wall time | 31 min (simulations 29 min) |

**Verdict.** Both designs are valid and above the 5% threshold (Ibex 14.7%, TPU 19.1%), so `plan.md` limit 3 stays:
zero-delay power maps under-state dynamic power by about 15 to 19% on these two designs, unevenly across tiles.
