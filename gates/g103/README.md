# G103: Leakage margins at the slow and fast process corners (RQ1) · INCONCLUSIVE (run 16-17 Nov 2026)

Registration: `registration.md` (queued as #111 before the run). Run: `run.sh main "<kit@corner>"` for the six
kit@corners one at a time in heavy slots (16 Nov 21:23 to 17 Nov 03:43), then `evaluate.py runs/main`. Output
`runs/main/` (git-ignored); record: `record/result.json` and `record/<kit>/<corner>/manifest.json`.

## Verdict: INCONCLUSIVE (ASAP7 RVT failed validity v1 at SS); the two valid kits pass (a)

| Kit | v1 library | v2 cross-check (<= 1%) | v3 power and loop | v4 TT control | (a) FF < TT < SS, all windows |
|---|---|---|---|---|---|
| IHP SG13G2 | SS, FF yes | worst 0.01% | yes | exact (0) | **yes** |
| ASAP7 RVT | SS **no** (4 of 8,576 states), FF yes | worst 0.18% | yes | 1.1e-16 | not scored |
| ASAP7 LVT | SS, FF yes | worst 0.14% | yes | exact (0) | **yes** |

Validity rule (registration): a kit failing any check is INCONCLUSIVE and so is the gate, with the valid kits'
orderings reported.

## Margins at 358.15 K (times the library leakage before runaway; window k0 / k1 / k2 / k3)

| Kit | FF | TT (G95) | SS | FF / TT | SS / TT |
|---|---|---|---|---|---|
| IHP | 913 / 908 / 910 / 917 | 4,607 / 4,582 / 4,587 / 4,619 | 29,801 / 29,625 / 29,638 / 29,790 | 0.198 | 6.45-6.47 |
| ASAP7 RVT (invalid at SS) | 18.9 / 17.1 / 17.5 / 18.6 | 25.2 / 22.8 / 23.3 / 24.9 | 35.0 / 31.6 / 32.4 / 34.6 | 0.748 | 1.39 |
| ASAP7 LVT | 3.37 / 3.08 / 3.14 / 3.32 | 4.5 / 4.1 / 4.2 / 4.4 | 6.25 / 5.69 / 5.81 / 6.16 | 0.75 | 1.39 |

The ratio to TT is almost the same in every window of a kit, because a corner scales nearly every cell's leakage by
a similar factor. IHP's corners move leakage far more than ASAP7's (FF about 5x, SS about 1/6.5, against 1.3x and
0.72x), in line with the per-cell ratios of the plumbing probe declared before registration.

## What it means

- **The LVT design at the fast corner has a margin of about 3x:** a leakage error or a hotter package of that size
  would make it run away at an 85 C ambient. The typical-corner 4x of G95 was already the smallest; the fast corner
  takes away a quarter of it.
- **IHP stays far from runaway at every corner** (900x at FF).

## Why ASAP7 RVT is invalid (diagnosed after the run; exploratory, the verdict stands)

The four failed states are `ICGx8DC` (`CLK * !ENA * !SE * !GCLK`) and `SDFHx1/2/3` (one scan state each), all at
25 C only: their settled leakage at SS wobbles by about 2% between 0.1 ms and 1 s of continuation (for example 550 to
558 pW), above the flatness tolerance, so leaklib kept the shipped value. None of the four cells occurs in the ASAP7
Ibex netlist (`6_final.v`: 0 instances among 20,658 cells), so the RVT SS margins above do not depend on them; they
are reported, not scored.
