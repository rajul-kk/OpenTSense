# Where the level-to-level change sits (17 Nov 2026)

`bash gates/g94/dry/locate_change.sh` (opentsense:g94b, 3d stack, step case seed 1, 78 slots of 5 ms, levels 0-5,
3D-ICE and PACT). `change.json`: per level against the previous one, per die, the largest change of the peak rise
at the coarser level's row ends, where it sits, and the largest change before and after 1, 5 and 25 ms.

| Level vs previous | Largest change, top / bot (K) | At t (ms), top / bot | After 5 ms, top / bot | After 25 ms, top / bot |
|---|---|---|---|---|
| 1 | 2.65 / 2.51 | 5.0 / 5.0 | 0.82 / 1.31 | 0.24 / 0.27 |
| 2 | 2.93 / 1.85 | 2.5 / 2.5 | 0.55 / 0.95 | 0.12 / 0.13 |
| 3 | 2.77 / 1.23 | 1.25 / 2.5 | 0.33 / 0.60 | 0.064 / 0.067 |
| 4 | 2.08 / 0.74 | 0.63 / 1.9 | 0.18 / 0.35 | 0.032 / 0.034 |
| 5 | 1.30 / 0.42 | 0.63 / 1.9 | 0.095 / 0.19 | 0.016 / 0.017 |

(3D-ICE. PACT's changes are within 0.06 K of these; its times of the largest change match except on the bottom die at levels 3-5, where it sits at 2.5, 2.5 and 1.9 ms; `change.json`.)

The largest change sits in the first few milliseconds after the power step, where the rise is steepest, and moves
earlier as the step shrinks: on the top die from 5 ms (level 1, the first row end) to 0.63 ms (levels 4 and 5, the
first and second row ends); on the bottom die, whose rise is slower, from 5 ms to 1.9 ms (the third and sixth row
ends at levels 4 and 5). Because the window it sits in moves with the level, the overall maximum looked stuck at
2-3 K in convergence.py. At any fixed time the change halves per level
(backward Euler's first order): after 5 ms from 0.82 / 1.31 K to 0.095 / 0.19 K, after 25 ms from 0.24 to 0.016 K.
So bar (c) has a floor that shrinks once it is taken at fixed times, or after a stated start-up window, not over
every row end. Which window and tolerance is the student's choice; the level then follows from this table
(about halving per level).
