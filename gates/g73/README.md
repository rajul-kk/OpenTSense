# G73: how hidden is a buried die?

**Verdict: PASS, with bar (b) confounded (2 Nov 2026).** Registration and Amendment 1: `registration.md`. Numbers: `result.json`. Picard data: `runs/main/picard.npz` (not in git).

| Bond | Sensors | Top DFS / error | Buried DFS / error | Equal-power DFS, top / buried |
|---|---|---|---|---|
| Micro-bump | 8 | 3.60 / 7.9% | 1.94 / 24.8% | 3.44 / 3.72 |
| Micro-bump | 16 | 5.69 / 7.4% | 2.60 / 23.4% | 5.57 / 6.10 |
| Micro-bump | 32 | 7.81 / 6.9% | 3.54 / 22.6% | 7.63 / 8.99 |
| Hybrid | 8 | 3.35 / 9.0% | 0.75 / 39.7% | 2.56 / 3.02 |
| Hybrid | 16 | 5.22 / 8.2% | 1.19 / 35.0% | 4.10 / 5.12 |
| Hybrid | 32 | 7.08 / 7.7% | 1.68 / 32.3% | 5.79 / 7.60 |
| Monolithic-like | 8 | 3.40 / 9.4% | 0.25 / 49.0% | 1.73 / 2.15 |
| Monolithic-like | 16 | 5.97 / 8.8% | 0.42 / 48.1% | 3.27 / 3.84 |
| Monolithic-like | 32 | 9.20 / 8.4% | 0.82 / 47.8% | 5.55 / 6.85 |

- **(a)** Spearman ρ = −0.93 (bar ≤ −0.8): met, but the 18 cases fall into two clusters. Within buried dies ρ = −0.98; within top dies −0.53.
- **(b)** Buried die has fewer DFS in 9/9: met, but the equal-power control gives 0/9. The bar measures the CPU's low power, not burial. Do not cite (b) as evidence that burial hides a die.
- **Not established:** the control equalises prior trace only; the dies' prior shapes still differ. A swapped stack (TPU buried) would be the direct test.
