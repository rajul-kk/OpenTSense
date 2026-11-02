# G74 registration (copied from fyp/todo-gates.md before the run)

### G74: Multi-die leakage runaway margin ρ(R·D) (RQ1) · REGISTERED
- **Why:** this is the 31 October mathematical lead 2, a multi-die version of the scalar runaway condition in Bhat, Gumussoy and Ogras (IEEE TCST 2020). It would explain the runaway verdicts in G31/G31b.
- **Set-up:**
  - **Cases:**
    - G31/G31b: sky130 ibex at 1.0 W/mm², HTC 1e4, 4 windows. All ran away.
    - G37: 4 windows, converged.
    - G41/G38: ASAP7 stacks, converged, with a small leakage share.
  - **Computation:** D = diag(∂P_leak/∂T) from the SPICE leakage curves, evaluated at the uncoupled operating point. R is the thermal response operator. The margin is ρ = spectral radius of R·D.
- **Pass if both hold:**
  - (a) ρ ≥ 1 exactly for the cases that ran away, and ρ < 1 for those that converged;
  - (b) for the converged cases, the predicted amplification 1/(1−ρ), evaluated at the fixed point, matches the measured ratio (coupled leakage-induced rise ÷ first-iteration rise) within 25%.
- **A fail means:** linearisation isn't enough, because the SPICE curve is not exponential (G35b). Try evaluating at the fixed point, or a row-sum bound.
- **Effort:** 1 to 2 days · **Output:** `gates/g74/`

## Amendment 1 (2 Nov 2026, before any ρ was computed)
How the bars are measured. No bar is loosened; two choices below make the gate stricter.

- **Inputs.** `gates/g74/prep.py` rebuilds every input from the exploratory archive and writes `out/inputs.npz` (bulk, not in git; its SHA-256 goes in the run's result).
  - **sky130:** `inst_loc.csv` no longer exists. Locations and masters come from `sens/phys/base_geom.csv`. It matches 41,627 of the 41,629 report rows by name; the other 2 are hierarchical rollups, which G31 also excluded (the report sum minus them equals G31's recorded native total).
  - **ASAP7:** G38's maps and G41's curves.
- **Broken SPICE points.** G41's 125 °C entries for `INVx1_R` and `INVx1_SL` are failed solves (8.9e5 W and 2.3e5 W). The 125 °C row is dropped for every curve; above 100 °C the curve extrapolates log-linearly from its last segment. G41's peaks stay below 100 °C, so its recorded loop never used that row.
- **Case list (20 cases, all must satisfy (a)).**
  - **Runaway (8):** windows k0 to k3 at 1.0 W/mm², HTC 1e4, leakage share 0.3, once with G31's leakage (exponential between the 25 and 100 °C library corners) and once with G31b's (SPICE curves by cell type). G31's model was withdrawn by G35b, so the registered "SPICE curves" strictly cover only G31b. It stays in because the registration names it, and D is taken from whichever leakage model that loop used.
  - **Converged (12):** G37 windows k0 to k3 at HTC 2e3 and 1e4 (8; the registration's "4 windows" did not name an HTC, so both are required), and G41 stacks 0 to 3 (4).
- **Thermal models.** Each case uses the solver its loop used: G31/G31b the periodic unit cell with k(T) in silicon; G37 the die-sized adiabatic-sided solver; G41 the G39 binned operator (202 bins, HTC 5e4).
- **R for the k(T) cases.** The registration says "thermal response operator", which does not settle constant k against k(T). Both are computed: the tangent of the nonlinear solve (what decides stability) and the constant-k operator. **Bar (a) must hold for both,** which is stricter than either alone.
- **D.** Central difference (±0.5 K) of the leakage function the loop actually uses, per grid cell or bin. The curves are piecewise log-linear, so an analytic slope would jump at table points.
- **ρ.** Largest-magnitude eigenvalue of R·D (ARPACK for the 32 × 32 cases, dense for the 202-bin case).
- **Uncoupled operating point.** The field with leakage fixed at 25 °C, as each exploratory script defines it.
- **"Ran away".** For G31b, the recorded rule: non-finite, or a rise above 175 K (200 °C), within 60 iterations. For G31, its rule: no convergence in 40 iterations. The loops are re-run here, and the measured status (not the recorded one) is what ρ is scored against.
- **Bar (b).** Measured on stack peak temperature: (T* − T_u) ÷ (T_1 − T_u), where T_u is the uncoupled peak, T_1 the peak after one iteration from T_u, and T* the converged peak (tolerance 1e-10 K). The predicted value uses ρ at the fixed point. "Within 25%" means |predicted ÷ measured − 1| ≤ 0.25, for all 12 converged cases.
- **G37 leakage lookup.** Continuous curve interpolation rather than G37's rounding to whole degrees, because the rounding would swamp rises of about 1e-5 K.
- **Plumbing check (not the gate).** Before any ρ is computed, the loops alone must reproduce the record, so a rebuilt input cannot pass silently:
  - G31b's 96-run map: every status equal, and peaks within 0.5 K;
  - G37: `py_peak_C` within 0.05 K;
  - G41: both die peaks within 0.05 K.
  A miss here stops the gate and is recorded as an amendment or a failure.
- **Reported, not gated:** ρ across all 96 runs of the G31b map (the same test on 12 runaway and 84 converged runs), and ρ at the fixed point of every converged run.
- **Plumbing result (2 Nov 2026, `runs/plumb`, no ρ computed):** G31b map 96/96 statuses equal, worst peak difference 6e-11 K; G37 worst 4e-6 K; G41 worst 0.00014 K. The inputs are faithful. The dev version of the loop used a 150 K ceiling by mistake; the recorded ceiling is 175 K of rise, and the gate run uses that. No status changed.
