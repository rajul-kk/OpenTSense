# G101: certified spectral radius and the tiles that set the runaway margin · PASS on (a), (b) and (c)

Registration: `registration.md` (bars fixed 15 Nov 2026 before the run; Amendment 1 prior art, Amendment 2 an
evaluator fix before scoring, no threshold changed). Cases: G95's 12 windows (IHP SG13G2, ASAP7 RVT and LVT ibex,
k0 to k3) at 358.15 K. They are not held out: G95 ran them, though not these quantities. Run:
`bash gates/g101/run.sh gates/g101/runs/main` (about 50 min, 2 GB cap). Record: `record/`.

| Bar | Result |
|---|---|
| Validity | G92e reproduction check passed. R > 0 everywhere (min 58 K/W on IHP, 4,686 K/W on ASAP7). D ≥ 0 at all 8,173 recorded calls. |
| (a) certificate | At every one of the 8,173 Newton iterates, over all bisection probes, the eigvals ρ lies inside the power-iteration Collatz–Wielandt bracket (largest relative gap 0). The runaway verdict is the same, and the bracket closes to 1e-12 in 5 to 13 iterations. Mean time per call: 1.8 to 9 ms, against 424 to 1,032 ms for eigvals (about 110 to 240 times faster). |
| (b) ranking | Scaling the leakage of the 51 top-w tiles by 1.1 lowers s* by 0.91 to 0.98%. That is at least as much as every baseline in all 12 windows. |
| (c) first-order law | pred = 1 - 1/(1 + 0.1 Σ_S w / Σ w) is within 0.7% of the measured drop in every window (bar 25%), and within 1.1% for the hot set (reported). That is about the resolution of the perturbed bisection, whose drops fall on a grid of about 7e-5 (0.7% of a 0.009 drop). |

## What it shows

- **Runaway can be certified without an eigendecomposition.** Power iteration gives a two-sided bound, and here it
  never disagreed with eigvals. Switching `electrothermal.rho` to it is a separate change, for the student to approve.
- **On these single-die stacks the left Perron vector adds no ranking information.** The Perron set overlaps the
  top-leakage set in 48 to 51 of 51 tiles and ties it in every window (strictly better in 0 of 12). Bar (b) passes,
  but the test favoured leaky tiles by construction: scaling a set's leakage by 1.1 adds power in proportion to the
  leakage it already holds. With w_j = (Rᵀy)_j·P_leak,j, the tie means Rᵀy varies little across tiles. That is
  inferred, not measured. The hottest tiles hold less leakage (overlap 4 to 14 tiles) and move s* 19 to 27% less.
  A perturbation of equal power per tile, or a two-die stack, would isolate the left vector; that is a new gate.
- **The sensitivity law is quantitative.** It predicts the margin change of a 10% local leakage change to about 1%, the bisection's resolution.
  So the margin's response to a local leakage change can be estimated from one solve at the boundary, instead of a
  new bisection of about 14 to 17 Newton solves (tested only for 10% changes on 5% of the tiles).
- **Reported only:** the right Perron vector (the runaway temperature mode) peaks at a different tile from the
  temperature peak in all 8 ASAP7 windows and 1 of 4 IHP windows. A runaway-watch sensor would go there, not at the
  hottest tile; G101 does not test that.

## Prior art (Amendment 1)

The margin-sensitivity formula is Greene, Dobson and Alvarado's, for voltage collapse in power grids
(IEEE Trans. Power Systems 12(1), 1997). Collatz–Wielandt bounds are standard Perron–Frobenius theory. What is new
here, as far as the searches found, is applying both to leakage–temperature runaway on a chip's tile grid.

## Not claimed

- Multi-die stacks, where Rᵀy may vary more and the Perron ranking could separate from the leakage ranking.
- Transient runaway.
- Corners other than G92e's.
- Sensor placement from the right vector.
