# G73 registration (copied from fyp/todo-gates.md before the run)

### G73: How hidden is a buried die? Do identifiability numbers predict the error? (RQ2) · REGISTERED
- **Why:** these are the 31 October mathematical leads 1 and 3. G13 tried this and failed, because its rank metric saturated at high SNR. This version uses noise-scaled, prior-aware measures.
- **Set-up:**
  - **Configurations:** 3 bonds from G54 (micro-bump, hybrid bond, monolithic-like) × 3 sensor budgets (8, 16 and 32 per stack), giving 9 configurations with 2 dies each.
  - **Noise:** σ = 0.65 K, the ASAP7 ring from G45.
  - **Steady-state sensing model:** A = H·G⁻¹·B, mapping die tile powers to sensors.
  - **Computed per die:**
    - (i) the noise-scaled smallest singular value of that die's block after projecting out the other die (Schur complement);
    - (ii) degrees of freedom for signal, i.e. the trace of that die's averaging-kernel block under the Bayes prior;
    - (iii) a Picard plot.
  - **Measured:** Bayes per-die power error (relative L2) over 160 real-activity workload draws.
- **Pass if both hold:**
  - (a) Spearman ρ between degrees of freedom for signal and measured per-die error is ≤ −0.8 across the 18 die-configurations;
  - (b) the buried die has fewer degrees of freedom for signal than the top die in all 9 configurations.
- **A fail means:** the prior dominates and the physics doesn't predict the error, which matches G67's "set by the prior" remark. Report it and fall back to empirical comparison.
- **Effort:** 2 days · **Output:** `gates/g73/`

## Amendment 1 (2 Nov 2026, before any identifiability number was computed)
How the measures are defined. The pass bars are unchanged.

- **Metric (i) as registered is degenerate.** With at most 32 sensors and 101 unknowns per die, the other die's block already spans the whole sensor space, so projecting it out leaves exactly zero for every configuration. This is the saturation that sank G13. It is replaced by the prior-aware Schur form the registration's "Why" asks for: the other die is marginalised as Gaussian noise, N_d = σ²I + H_o C_oo H_oᵀ, and (i) is the smallest singular value of N_d^(−1/2) H_d C_dd^(1/2). The largest singular value and the full spectrum are also stored. (i) is not part of either bar.
- **Operators.** The saved G39 (micro-bump) and G54 (hybrid, monolithic-like) operators: 202 unknowns, 101 per die (100 block bins plus 1 dark). TPU is the top die, CPU the buried die.
- **Budgets.** 8, 16 and 32 per stack, split equally between dies, placed with G39's greedy D-optimal rule on the training prior only, candidates inside the active block.
- **Prior.** Sample mean and covariance of seeds 300 to 419 (G42's training split), plus G39's ridge of 1e-3 × trace/n.
- **The 160 draws.** G42 has only 200 draws in total, so 160 cannot be both held out and leave a training set. New draws are made with G42's generator at seeds 500 to 659, which no exploratory result used. Their readings are y = H A p + noise, so the estimator's model is exact here, and there is no noise inflation (it would make DFS and the estimator disagree). 10 noise repeats per draw, seed 73.
- **Measured error.** G42's `pow_rel`: mean over draws of ‖p̂ − p‖ / ‖p‖ on the die's 100 block bins, from the cross-die Bayes estimate.
- **DFS (ii).** trace of the die's 101 × 101 block of the averaging kernel K H under the same prior and σ = 0.65 K. The 100-bin version is also stored.
- **Picard (iii).** Singular values and |uᵢᵀ(y − ȳ)| of the whitened operator, stored per configuration for the figure.
- **Plumbing check (not the gate).** Before any identifiability number is computed: (1) G42's generator reproduces stored power at seeds 300 to 499 within 1e-9 W; (2) this estimator, with G54's 16 sensors, recorded truth and inflation search, reproduces G54's σ = 0.65 `pow_rel` within 0.03 for both dies on all 3 bonds. A miss stops the gate.
- **Reported, not gated: equal-power control.** The buried CPU die draws about one-fifth of the TPU's power, so bar (b) could pass because of power, not burial. DFS is recomputed with each die's prior rescaled to equal trace. If the buried die still has fewer DFS in all 9 configurations, burial is the cause; otherwise the bar is confounded and that goes in the verdict.
- **Plumbing result (2 Nov 2026, `runs/plumb`, no identifiability number computed):** generator error 0.0 W at seeds 300 to 499; estimator within 0.0016 of G54 on both dies of all 3 bonds.
