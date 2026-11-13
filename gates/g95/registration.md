# G95 registration (written 13 Nov 2026, before the gated run; bars fixed now)

### G95: Does the spectral test separate runaway from convergence at rho ~ 1, and what does it predict? (RQ1) · REGISTERED

- **Why.** G74 passed, but its nearest cases were rho = 0.38 and 3.9, so the boundary rho = 1 was never tested, and
  its bar (b) was weak (amplification at most 1.05). Draft and dry findings: `draft.md`.
- **Cases (held out).** G92e's three designs (IHP SG13G2, ASAP7 RVT, ASAP7 LVT ibex; four windows each), G92e's
  libraries, operators and stacks, at G92e's **hot** ambient, **358.15 K**. Leakage is scaled by s; s* is the
  critical scale found by bisection (rtol 1e-4) on Newton's status (`runaway.critical_scale`), and f = s / s* is
  taken on the grid 0.5, 0.8, 0.9, 0.95, 0.99, 0.999, 1.001, 1.01, 1.1, 1.5. These cases have not been run.
- **Pilot (disclosed).** The same sweep at the nominal ambient, 300 K (`dry/pilot300/`, scored by this gate's
  `evaluate.py`): bars (a), (b) and (c) all held on all 12 windows. Bar (c)'s region f <= 0.8 was chosen from that
  pilot (1/(1 - rho_hot) within 25% of A up to f = 0.8 on every kit, worst 20.3% on ASAP7 RVT; at f = 0.9 up to
  30.5%). Bars (a) and (b) were fixed by the student on 12 Nov, before any sweep on these designs.
- **Method.** `sweep.py` per kit (`run_sweep.sh gates/g95/runs/main hot`), in `opentsense:g75spice` capped at 2 GB.
  Amplification A on the peak tile is (T* - T_u) / (T_1 - T_u) with T_u at every instance's leakage at the ambient
  temperature (`sweep.amp_ambient`); G74's A (baseline at 25 C) is reported as A_25C. rho_hot is the spectral radius
  of R diag(dP_leak/dT) at the converged temperature. Scoring: `python gates/g95/evaluate.py gates/g95/runs/main hot`.
- **Noise floor (`plan.md` 2.1).** The sweep is deterministic (same inputs give the same numbers to round-off), so the
  floor is 0 and the factors stay as written.
- **Validity (INCONCLUSIVE, not FAIL).** Every window's fixed point at the real leakage (s = 1, 358.15 K) must reproduce
  the peak G92e recorded for its hot case (`result.json` c.cases.<window>_hot.peak_K) within 1e-6 K; `sweep.py` stops
  otherwise and the kit's output is missing.
- **Pass if all hold, on every kit and window:**
  - **(a) Classification:** every f <= 0.999 converges and every f >= 1.001 runs away (delta = 0.001), and on every
    converged point a 10^5-iteration Picard solve converges and agrees with Newton within 1e-6 K.
  - **(b) Boundary:** rho at the last converged bisection point s_lo is >= 0.97. (The saddle-node law at the bisection
    tolerance gives 1 - sqrt(4e-4) = 0.98; the draft's "about 0.97" was an arithmetic slip, and 0.97, the value the
    student accepted, is kept: it is the looser bound.)
  - **(c) Prediction:** for every converged f <= 0.8 (at least two points), |A - 1/(1 - rho_hot)| / A <= 0.25.
- **Reported, not gated.** 1/f at the real leakage (the leakage margin) per window; A against 1/(1 - rho_cold) and
  A_25C; the fitted constant of 1 - rho ~ c sqrt(1 - f) at f = 0.99 and 0.999; Newton iterations and monotonicity;
  how the margin changes from 300 K to 358.15 K. G74's 20 cases are not re-classified here: they need G74's own k(T)
  loop (continuity only; a later note if done).
- **A fail means.** (a): the spectral test is not a safe margin on real leakage tables at a hot ambient. (b): the
  bisected boundary is not where rho reaches 1. (c): 1/(1 - rho_hot) does not predict amplification even far from the
  boundary at 358 K; the report quotes the leakage margin f instead.
- **Not claimed.** Transient runaway (G94); k(T) operators; process corners other than G92e's; one stack per kit.
- **Code and output.** `sweep.py`, `evaluate.py`, `run_sweep.sh` here; output `runs/main/` (git-ignored); after the run,
  `python scripts/record_gate.py g95`.

Amendments go below, dated, each with the reason. Never re-run until it passes.
