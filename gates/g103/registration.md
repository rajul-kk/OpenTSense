# G103 registration (written 16 Nov 2026, before the gated run)

### G103: Leakage margins at the slow and fast process corners (RQ1; goals.md 13) · REGISTERED

- **Why.** G95's leakage margins (how many times the library's leakage the design can take before thermal runaway,
  at an 85 C ambient) are at the typical corner only: IHP 4,580-4,620, ASAP7 RVT 22.8-25.2, ASAP7 LVT 4.1-4.5.
  Process corners change leakage several times, which moves the margin directly.
- **Corners.** IHP SG13G2: its PDK's `mos_ss` / `mos_ff` and `dio_ss` / `dio_ff` sections. ASAP7: the SS and FF
  BSIM-CMG cards of asap7_pdk_r1p7 (`7nm_{SS,FF}_160803.pm`, commit 58d72c9d), converted by the converter that made
  the TT card (it reproduces the image's TT card byte for byte); image `opentsense:g103` = `g75spice` + those cards
  (`docker/Dockerfile.g103`). Supply stays at each kit's nominal VDD (a process corner only).
- **Method, per kit and corner** (`run.sh`; kits as G92e: IHP, ASAP7 RVT, ASAP7 LVT): leakage libraries by
  `leaklib.py <kit>@<corner>` (G92e's generator; only the device models change); `leak.py` at the same corner as the
  cross-check; OpenSTA power of G92e's four windows at each library temperature (G92e's `power.tcl`); then
  `margin.py`: G95's operator, solver settings and bisection (rtol 1e-4) at 358.15 K give each window's margin s*.
- **Noise floor.** Deterministic (G95: same inputs give the same numbers to round-off), so 0; the bar is an ordering.
- **Validity (per kit and corner; any failing makes that kit INCONCLUSIVE).**
  - **(v1)** Library: every planned state solved at all five temperatures and no cell kept shipped (G92e (a)).
  - **(v2)** Cross-check: the library against `leak.py` at the same corner within 1% at 25, 50, 75 and 100 C (IHP:
    G53's six combinational states; ASAP7: INVx1 and NAND2x1). IHP's `dfrbp_1` reference (G92e's 1 ms deck) is not
    rerun at corners.
  - **(v3)** Every OpenSTA run reports power for the design (a `Total` line), and at the real leakage (s = 1) the
    loop converges at 358.15 K. A missing or broken output also makes the kit INCONCLUSIVE.
  - **(v4) TT control, per kit:** `margin.py` on G92e's own TT run (`../g92e/runs/main/<kit>`) reproduces G95's
    recorded margin within 1e-6 relative in every window (same operator, settings and bisection), so the corner
    margins and G95's TT margin come through one path.
- **Pass if all three kits are valid and, on each,** **(a)** margin(FF) < margin(TT) < margin(SS) in each of the four windows, with
  TT = G95's recorded margin (1 / f_nominal, `../g95/record/result.json`).
- **FAIL** if any valid kit breaks (a); otherwise a kit failing validity makes G103 INCONCLUSIVE (the valid kits'
  orderings are still reported).
- **Reported, not gated.** Margin per window, kit and corner; its ratio to TT; total leakage at 358.15 K per corner.
  Within-die variation (the PDKs' mismatch models) is not run.
- **A fail means.** Leakage at a corner does not move the margin in the expected direction: a plumbing error (wrong
  models reaching the solver) or a temperature slope that reverses the order; diagnose before quoting any corner.
- **Not claimed.** Corners are global (every device at the corner); no within-die variation, no voltage or ageing
  corners; timing at corners is goal 14. **Only leakage is at the corner:** `leaklib` rewrites the leakage of the
  shipped TT libraries, so internal and switching power stay at TT in every corner's margin.
- **Seen before registration (declared).** A plumbing probe (`dry/corner_probe.py`, `corner_probe.json`) of
  leak.py's cells at 25 C: IHP SS/TT 0.16-0.31 and FF/TT 3.5-9.3; ASAP7 SS/TT 0.67-0.71 and FF/TT 1.39-1.43. No
  library, power or margin has been computed at a corner. Each corner directory's manifest names the image and the
  sha256 of the model files it loads; a kept output from another image stops the run.
- **Code and output.** `run.sh <run_id> "<kit@corner ...>"`, `margin.py`, `evaluate.py`; output `runs/main/`.

Amendments go below, dated, each with the reason. Never re-run until it passes.
