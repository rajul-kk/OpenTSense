# G81e: Memory-die power follows the workload (RQ2) · INCONCLUSIVE (run 16 Nov 2026)

Registration: `registration.md` (queued as #106 before the run). Run: `step2/g50a_check.py`, `step2/run.py
runs/step1-main runs/main`, `step2/evaluate.py runs/main`. Output `runs/main/` (git-ignored); record:
`record/{result,manifest}.json`.

## Verdict: INCONCLUSIVE (validity v3 failed)

| Validity | Result | Held? |
|---|---|---|
| (v1) trace | step 1: 20 of 20 programs (before registration) | yes |
| (v2) controller | 0 violations in every command trace; G50a reproduced exactly (6.2187 pJ/bit) | yes |
| (v3) energy model within 0.1% of DRAMPower per program | 16 of 20; nsichneu 2.4e-3, nettle-aes 1.4e-3, xgboost 1.2e-3, nettle-sha256 1.2e-3 | **no** |

The bars were scored but decide nothing while v3 fails: (a1) 17 of 19, (a2) 12 of 19, (b) 18 of 19 (15 needed).

## Why v3 failed (diagnosed after the run; the verdict stands)

Core energy and the shared background match DRAMPower exactly on nsichneu; the whole gap is interface dynamic energy,
which the model under-predicts by 3.4 to 4.1 pJ per data burst in every program checked (nsichneu, nettle-aes,
nettle-sha256, xgboost, tarfind, crc32), not per back-to-back burst (4.5 to 7.7 pJ there), so it scales with traffic.
Cause: the dry fit's calibration traces were all random-address traffic, where every cache line is ACT, two bursts
and PRE, so the command count is a fixed multiple of the burst count and the per-command and per-burst interface
coefficients are not separately identified; only their sum for that mix is. Real programs read mostly row hits
(nsichneu: 140,486 bursts after 2,060 ACTs), outside that mix. The held-out traces shared the calibration mix, so
the dry check (2.2e-4) could not see it. Lint: calibrate a linear model on traces whose features vary
independently, and hold out a trace from outside the calibration mix.

## Reported (not a verdict)

- Dynamic power is 0.15% (crc32-class) to 81% (nsichneu) of the memory die's total; mean dynamic power spans
  6.5e-5 to 0.195 W over the 19 programs (median program sglib-combined).
- (a2)'s lowest per-program Pearson (worst seed): nsichneu 0.13, xgboost 0.79, tarfind 0.82; most programs 0.85-0.99.

## Next

A follow-up gate (G81f): refit the energy model with calibration traces that vary row hits and commands per burst
independently (sequential, strided and random traffic), check it on a held-out row-hit trace, then rerun with the
same bars. The bar results above are known before that registration and must be declared there.
