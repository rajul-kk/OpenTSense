# G92d result: FAIL on (a) for IHP and ASAP7 RVT; ASAP7 LVT PASS; (b) and (c) PASS on all three kits

Registration: `registration.md` (5 Nov 2026), with Amendments 1 and 2 (6 Nov). Run: `gates/g92d/run.sh main`, resumed for IHP
(`RESUME=1`, `REF_J=2`), launched 6 Nov, finished 7 Nov 02:36. Outputs: `runs/main/{ihp,asap7,asap7_lvt}/`, log `run_main.log`.
Wall time: IHP 16,295 s (almost all of it the `ref_dfrbp` step, including about 3 h of laptop standby), RVT 2,725 s, LVT 3,314 s.

## Verdict per kit

| Kit | (a) | (b) | (c) | Verdict |
|---|---|---|---|---|
| IHP SG13G2 | **fail** (reference not flat) | pass | pass | FAIL |
| ASAP7 RVT | **fail** (2 states not flat by 1 s) | pass | pass | FAIL |
| ASAP7 LVT | pass | pass | pass | PASS |

The gate needs all three kits, so **G92d is a FAIL.**

## (a) in detail

**IHP.** Everything in (a) passed except the `dfrbp_1` cross-check, which fails by rule because its reference is not flat:
- `ref_dfrbp.py` flatness |I(100 µs)/I(10 µs) − 1|, bar 0.5%:

  | | 25 °C | 50 °C | 75 °C | 100 °C |
  |---|---|---|---|---|
  | Q = 0 | 0.24% | **0.67%** | **0.58%** | 0.00% |
  | Q = 1 | **1.14%** | **0.81%** | 0.00% | 0.00% |

  The values move up and down between windows (Q = 1, 25 °C: 575.3 → 560.8 → 567.2 pW at 1 / 10 / 100 µs), so this looks like
  solver noise in the reference, not slow settling. Its 100 µs value for Q = 1 at 25 °C (567.2 pW) equals the library's settled
  value. Not gated, not used for the verdict.
- 645 states, 0 not ok, 0 retried; 135 captured plans, all settled at the 1 ms stage at every temperature.
- G53 combinational cross-check: max |rel diff| 1.5e-5. Settling validation (`sdfrbpq_1`): 657.94 vs 658.0 pW (−0.01%).
- G92c regression: 2,500 values, max rel diff 0. Seeded DC: 0 flips, max disagreement 4.7e-6.

**ASAP7 RVT.** Everything passed except 2 of 8,576 states, both `SDFHx3`, which never went flat by 1 s at 25 °C:
- `(CLK * D * SE * SI * QN)`: 257.84, 252.75, 250.84, 253.39, 251.48 pW at 0.1 ms … 1 s.
- `(CLK * !D * SE * !SI * QN)`: 238.11, 242.56, 240.65, 242.56, 240.65 pW.
- The jumps are 1.9–2.6 pW, three to four steps of the 0.64 pW quantum seen in the dry run, above both the 2 pA × VDD floor
  (1.4 pW) and 0.5%. The second trace alternates between two values.
- `leak.py` cross-check: max 0.23% (INVx1 / NAND2x1). Settling validation: DHLx1 −0.44%, ICGx1 +0.02%.
- G92c regression: 40,619 values, max rel diff 0. One state used its retry (`NOR5xp2`) and solved.
- Seeded DC (reported only): 3 flips in 468 plans (DFFHQx4 at 25 °C, SDFHx2 at 50 °C), median disagreement 1.3e-4.
- Settled at stage, 25 °C: 1 ms 218, 10 ms 220, 100 ms 16, 1 s 14; all others by 10 ms.

**ASAP7 LVT.** (a) passed: 0 not ok; `AOI311xp33_L` (G92c's solver stop) solved on its retry; cross-check max 0.015%;
G92c regression exact; seeded DC 0 flips; all 470 captured plans settled at 1 ms.

## (b), (c) and reported numbers
- (b) OpenSTA plumbing and (c) the loop passed on all three kits.
- IHP and LVT loop results match G92c (largest peak difference 5e-6 K and 2e-4 K).
- **RVT ibex design leakage is higher than G92c's**, e.g. k0 at 100 °C 46.9 vs 39.3 µW (+19.6%); nominal-case ρ 0.0019 vs
  0.0016, hot 0.0148 vs 0.0122. **Cause found:** G92c left 4 cells unsolved, and an unsolved cell keeps its shipped Liberty
  values. One of them, `DFFASRHQNx1`, has 1,665 instances in ibex. G92d solves it. Captured-state values themselves agree with
  G92c at 100 °C (median ratio 1.000, max 1.001). G92d's unsolved cell, `SDFHx3`, has no instances in ibex, so its failure does
  not affect the design numbers.
- **Consequence for G92c:** G92c's finding "settling lowers RVT ibex leakage at 100–125 °C by about 16%" compared libraries in
  which `DFFASRHQNx1` was handled differently, so it must be rechecked before it is used.
- 150 ns ÷ settled at 25 °C (median): IHP 1.37, RVT 1.37, LVT 1.24.

## What a fail means here
Both fails are measurement noise at the 1% level, not a wrong method:
- IHP: the cross-check reference wobbles by up to 1.1% between averaging windows.
- RVT: 2 states (unused by ibex) alternate by about 2 pW at 25 °C.

Next: G92e changes only the flatness measurement (dry runs in `../g92e/dry/`).
