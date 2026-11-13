# G92e result: PASS on (a), (b) and (c) for all three kits

Registration: `registration.md`. Run: `gates/g92e/run.sh main`, started 11 Nov 2026 15:31; IHP's `ref_dfrbp` step (1 ms
transient, four runs) ran in container `1a6ddc2800dd` to 13 Nov, then `RESUME=1 run.sh main all` finished IHP and ran
ASAP7 RVT and LVT, ending 13 Nov 07:41 (exit 0). Outputs: `runs/main/{ihp,asap7,asap7_lvt}/` (git-ignored), log
`runs/main/run.log`; record: `record/<kit>/{result,manifest}.json`. Wall time: IHP 137,809 s (almost all of it the 1 ms
reference), RVT 4,171-4,427 s, LVT 3,798 s.

## Verdict per kit

| Kit | (a) | (b) | (c) | Verdict |
|---|---|---|---|---|
| IHP SG13G2 | pass | pass | pass | PASS |
| ASAP7 RVT | pass | pass | pass | PASS |
| ASAP7 LVT | pass | pass | pass | PASS |

**G92e is a PASS.** G92d's two failures are gone: IHP's `dfrbp_1` reference is flat at 1 ms, and RVT's `SDFHx3` states
settle once the stage current is averaged over the last 10% of the stage.

## (a) Library equals SPICE

| Check | IHP | ASAP7 RVT | ASAP7 LVT |
|---|---|---|---|
| Cells / states / not ok | 84 / 645 / 0 | 202 / 8,576 / 0 | 202 / 8,576 / 0 |
| Kept at shipped values | none | none | none |
| Retries used | 0 | 1 (NOR5xp2) | 2 (AOI311xp33) |
| Captured plans, settled by 1 s | 135 of 135 | 470 of 470 | 470 of 470 |
| Cross-check, max rel. difference (bar 1%) | 1.5e-5 (`dfrbp_1` vs 1 ms ref) | 0.23% (INVx1, NAND2x1) | 0.015% |
| Settling validation (bar 1% at 25 °C) | sdfrbpq_1 -0.01% | DHLx1 -0.06%, ICGx1 -0.35% | none listed |
| G92d regression, non-captured values | 2,500 equal | 40,619 equal | 40,615 equal |
| G92d regression, captured (max / median) | 8.4e-7 / 1.9e-8 | 1.2% / 1.6e-4, none outside 2.8 pW | 0.12% / 1.9e-5 |

`dfrbp_1` reference flatness |I(1 ms)/I(100 µs) − 1|, bar 0.5%:

| | 25 °C | 50 °C | 75 °C | 100 °C |
|---|---|---|---|---|
| Q = 0 | 0.20% | 0.00% | 0.00% | 0.00% |
| Q = 1 | 0.00% | 0.00% | 0.00% | 0.00% |

The windows show slow settling, not noise: Q = 0 at 50 °C reads 1,075.1, 1,082.4 and 1,082.4 pW at 10 µs, 100 µs and 1 ms.

## (b) OpenSTA plumbing and (c) loop

- (b) Every window's shipped leakage equals the `leak.py` reference where there is one (IHP, RVT), and dynamic power is
  identical; LVT has no `leak.py` reference, as in G92d.
- (c) Every case converged. ρ and peak shift against a fixed 25 °C library:

| Kit | nominal ρ / shift | hot ρ / shift | stress ρ / shift |
|---|---|---|---|
| IHP | ~1e-5 / 0.00 K | ~8e-5 / 0.002 K | 0.45-0.53 / 6.7-8.4 K |
| ASAP7 RVT | 0.002 / 0.04 K | 0.015-0.016 / 0.42-0.47 K | 0.47-0.53 / 9.8-12.3 K |
| ASAP7 LVT | 0.015-0.017 / 0.32-0.38 K | 0.089-0.099 / 2.9-3.2 K | 0.46-0.54 / 12.0-14.3 K |

## Reported

- Design leakage at 25 °C (window k0) against G92d: IHP equal (to 6e-9 relative), RVT +0.04%, LVT +0.003%.
- RVT's seeded-DC cross-check flips on 3 states (DFFHQx4 at 25 °C, SDFHx2 at 50 °C); the settled values stand, as
  registered (the DC solve is a cross-check only). Agreement elsewhere: max 0.83% (RVT), 0.11% (LVT).
- 150 ns ÷ settled at 25 °C: median 1.37 (IHP), 1.85 (RVT), 1.24 (LVT), so a 150 ns capture overstates leakage of
  captured states by about a quarter to a half.
- Shipped ÷ SPICE at 25 °C, reachable states: median 1.17 (IHP), 1.29 (RVT), 1.43 (LVT); the shipped libraries are
  not usable for leakage at temperature.

## Not claimed

As registered: the three kits' typical corners, the states the generator plans, G92d's cases, stacks and loop.
