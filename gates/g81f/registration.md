# G81f registration (written 16 Nov 2026, after G81e, before the gated run)

### G81f: Memory-die power follows the workload, with an identified energy model (RQ2) · REGISTERED

- **Why.** G81e was INCONCLUSIVE: its validity bar (v3) failed on 4 of 20 programs (worst 2.4e-3 against 1e-3)
  because the energy model's interface coefficients were not identified. Its calibration had 4 traces for 4 interface
  coefficients (exactly determined) and only random traffic, where commands are a fixed multiple of bursts
  (`../g81e/README.md`). G81f refits the model and changes nothing else.
- **What changes from G81e.** Only the energy model: `dry/fit_energy2.json`, fitted by `dry/fit_energy2.py` on 16
  calibration traces varied in regime (refresh only; random, sequential and strided lines), read/write mix, load,
  length (0.4M to 5M CPU cycles) and arrival (uniform or packed into dense phases). Interface fit residual 0.38%;
  condition number of the column-scaled interface features 10.0. Held out, 6 traces outside the calibration's range
  on purpose (up to 132k bursts per 1M cycles against the calibration's 59k; lengths 0.3M and 6M; regimes interleaved
  request by request), scored through G81e step 2's per-window path (the path v3 scores): worst interface error
  0.40%, worst total 1.9e-4 (interface energy is about 5% of the total there, about 2% on nsichneu). Per data burst
  the interface coefficient rose from 25.8 / 23.5 pJ (read / write, G81e's fit) to about 36; per command it fell
  from 7.2 to about 1.4 pJ.
  - A first refit (`dry/fit_energy.py`, `fit_energy.json`, kept as run) was reviewed as too easy a check: its held-out
    traces were time-mixes of its calibration regimes at one length and modest density, scored on the whole-trace
    path. Its numbers are not used.
- **Everything else as G81e's registration**, including its pre-run fixes: traces (step 1), hierarchies, controller,
  seeds, the floor (mean and range over seeds 1-5), bars (a1), (a2), (b) with 15 of 19 programs, validity (v1)-(v3),
  reported numbers. Code: G81e's `step2/` run unchanged through `run.py` here, which only points it at the new fit (and labels the
  manifest G81f). Output `runs/main/` under `gates/g81f`; run in a heavy slot of 2 GB as G81e.
- **Seen before registration (declared).** G81e's full run with the old fit: (a1) 17, (a2) 12, (b) 18 of 19; dynamic
  share of total 0.15% to 81%; lowest (a2) Pearson nsichneu 0.13, xgboost 0.79, tarfind 0.82. The refit moves energy
  from commands to bursts, so dynamic power and its correlation with fills change; how much is not known before the
  run. The bars are G81e's, unchanged; none was set or moved after those numbers were seen.
- **A fail or INCONCLUSIVE means** as G81e. If v3 fails again, the linear model is not adequate for row-hit traffic
  and the memory die stays parametric with that reason.

Amendments go below, dated, each with the reason. Never re-run until it passes.
