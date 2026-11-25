# G108 draft: the buried-die sensor budget with an active-block keep-out (goal 21)

**Question.** With the top die's sites fixed and the buried die's sensors kept outside the active block and its
keep-out ring, does reducing the buried die from eight sensors to two cost at most G107's 0.25 K in whole-die
RMSE? Ask separately for independent and die-wide correlated offsets. At fixed budgets, how much RMSE does the
keep-out add to A-optimal greedy placement?

**Why.** G107 passed its two-vs-eight bars on unrestricted uniform layouts, while its unrestricted greedy sites
fell inside the buried CPU die's active block ([G107 record](../g107/record/result.json), [sites](../g107/dry/budget.json)).
G104's unrestricted-to-outside uniform cost was +0.08 K on top and +0.06 K on the bottom with independent offsets,
with eight sites per die and both dies' layouts changing ([G104 record](../g104/record/result.json)). G108 fixes
the top die and varies the buried budget and restrictions; neither prior comparison answers that question.

## Method (dry; [runner](dry/keepout.py))

- **Cases.** G84's recorded case set and program-grouped train/cal/test splits, unmodified: G71's steady-state TPU
  top die and buried CPU die, with the same G84 eight top sites in every arm. The runner checks the canonical
  case-set fingerprint from G107 and imports the fit and original sites from G107's dry code. G84's builder
  uses G71's `act3` active-block map for the CPU and TPU power footprints ([case builder](../g84/make_cases.py)).
  Restrict only the buried die, using G104's map-derived rectangle expanded by its two-cell ring and its
  `grid_in` outside-grid rule ([site helpers](../g104/dry/sites.py)).
- **What is compared.** Two and eight buried sites under each of four layouts: G107 unrestricted uniform;
  G104-style outside uniform; unrestricted greedy A-optimal; and outside greedy A-optimal. Uniform layouts use
  each budget's grid rule, not a nested subset. Greedy starts with the same eight top sites for both arms; two
  is the prefix of eight, and the unrestricted two must reproduce G107. Use G107's single train-only scalar
  placement noise for both greedy arms to isolate the effect of changing the mask. Per-arm estimator noise
  still follows the datasheet model on that arm's train-only sensor temperatures.
- **Readings.** Same `ring_osc` profile, chip seeds 1-5, salt 107, independent offsets and G105's (0.8, 3 mm)
  offsets as G107 ([G107 registration](../g107/registration.md); the offset pair from [G105's draft](../g105/draft.md)). Each offset-model/chip unit reads the ordered union once, retaining G107's original union order as a prefix and
  appending G108 sites. Each arm selects columns with `bench.readings.subset` so all shared sites carry identical
  draws within a unit. Enlarging the union can change the sensor draws,
  including on existing sites; unrestricted controls must be rescored inside G108, not subtracted from
  published G107 scores. Independent and correlated offsets are analysed separately.
- **Scoring.** G107's average and field-model ladder through `bench.score`: fit the field once from train fields,
  score on test, and take each die's mean over program groups of the group median RMSE. Subtract the two arm
  scores within a chip and take the mean over chips, with standard
  error across chips. The two uniform arms with the keep-out are the primary contrast; the direct bridge
  to G107's unrestricted eight-site reference is reported separately, as it changes both budget and mask.

## Dry results

Run 20 Nov 2026 (date from `context.md`; the logs carry no timestamp). The reported result is the full run, chips
1-5 and both offset models ([dry/keepout.json](dry/keepout.json); `dry/keepout.log` ends rc=0): 48.2 s wall,
2.06 GiB peak working set (2,208,784,384 B), 43.9 s of it setup including the fit and placement (91%). The earlier
one-chip slice ([dry/slice.json](dry/slice.json)) is a cross-check only: its placement and chip-1 scores equal the
full run's, and its launcher logged an empty rc (`dry/slice.20261120-170737-909.log`, the handle bug fixed since).
Both runs came from the runner before its write-check and telemetry changes; the scoring path is unchanged.
Buried-die RMSE differences, mean over chips +- SE:

| Contrast (buried die) | Independent offsets | Correlated (0.8, 3 mm) |
|---|---|---|
| **2 vs 8 outside-uniform (proposed bar)** | +0.042 +- 0.054 K | -0.027 +- 0.126 K |
| 2 vs 8 unrestricted uniform (G107's layouts) | +0.082 +- 0.040 K | +0.086 +- 0.087 K |
| keep-out cost, uniform, 2 sites | 0.000 (same sites) | 0.000 (same sites) |
| keep-out cost, uniform, 8 sites | +0.040 +- 0.029 K | +0.113 +- 0.056 K |
| keep-out cost, greedy, 2 sites | +0.153 +- 0.138 K | +0.111 +- 0.100 K |
| keep-out cost, greedy, 8 sites | +0.152 +- 0.032 K | +0.135 +- 0.094 K |
| 2 vs 8 outside-greedy | +0.109 +- 0.111 K | +0.023 +- 0.107 K |

What the dry run shows for the design:
- **The two-site uniform layout already avoids the block.** G107's 2-site uniform sites have no keep-out intrusion
  (`placement.buried_sites_in_keepout`), so outside-uniform 2 is the same layout and only the 8-site reference
  changes (G107's 8-site uniform has one site inside). Bar (a)/(b) therefore asks whether two sites cost at most
  0.25 K against an 8-site reference moved out of the block, not whether the keep-out costs the 2-site layout
  anything.
- **The keep-out costs greedy placement about 0.15 K with independent offsets** at both budgets (+0.111 / +0.135 K
  correlated). Restricted greedy and restricted uniform at 8 sites are not resolved apart (greedy minus uniform
  +0.019 +- 0.027 K independent, -0.027 +- 0.056 K correlated).
- **Resolution.** If the chip-to-chip variance stays as in the dry run, 10 held-out chips give SEs of about 0.038 K
  (independent) and 0.089 K (correlated), so a 0.25 K bar sits about 5.5 and 3.1 SEs above the dry means.
- **What the primary contrast measures** (Sol, G108-D1). Both 2-site arms are (30,15) and (30,45) on the buried die;
  the 8-site rule outside the block swaps (30,30) for (50,50). On shared readings the primary delta equals the
  unrestricted 2-v-8 delta minus the 8-site keep-out cost (correlated: 0.086 - 0.113 = -0.027 K), so its negative
  correlated value comes from the reference moving, not from a gain at two sites. It answers "do two feasible sites
  meet the budget against eight feasible sites on these cases"; the effect of the keep-out itself is the same-count
  masked-vs-unmasked contrast (reported, or primary if the student wants that question).

## Proposed gate (student to fix, not registered)

- **(a) Independent offsets:** buried-die RMSE of two outside-uniform sites minus eight outside-uniform sites
  no more than **+0.25 K** in the paired mean across chips.
- **(b) Correlated offsets:** the same bar, applied separately to the correlated model.
- **Proposed held-out chips:** seeds **31-40**, disjoint from G107's 21-30 ([G107 registration](../g107/registration.md)) and this dry run's 1-5; keep salt 107
  and the same ordered union. The dry runner cannot score these seeds.
- **Noise floor:** use paired chip standard errors from the full dry run to size the resolution, not to tune the
  0.25 K engineering tolerance inherited from G107. As a planning reference only, G107's unrestricted dry
  2-vs-8 buried-die SEs were 0.02 K independent and 0.12 K correlated ([G107 dry scores](../g107/dry/budget.json),
  [summary](../g107/draft.md)); G108's
  changed layouts and read universe need their own estimates. Before freezing, check whether the chosen chip
  count can distinguish useful effects from chip spread and whether the proposed bars are informative on the
  dry data. The future bars are one-sided mean budgets, not claims of statistical equivalence.

**Validity (otherwise inconclusive).** Before any held-out scoring, reproduce the dry placements, union order,
and placement noise; verify that the case fingerprint, code, configuration and mask provenance agree with the
registered inputs and remain unchanged. Independently verify in the future evaluator that every arm has the same
eight top sites, the named count of distinct buried sites, no ineligible buried site in an outside arm, the
registered chips/offsets with a full finite record, and the positive end marker. Check the geometry against the
original G84 map/grid and do not accept a shape match alone as proof of registration. Dry and held-out records
must stay separate; no score or bar uses a mixture of the two.

**Reported, not gated.** Same-budget outside minus unrestricted greedy at two and eight sites with matched
placement noise; outside-greedy two minus eight; unrestricted-uniform two minus eight; outside-uniform two minus
G107-style unrestricted eight; outside minus unrestricted uniform at both budgets; by-chip differences and their
SEs, both dies' absolute RMSE and peak error, average baseline and group-bootstrap comparisons, and sites/overlap.
In particular, keeping the greedy penalty descriptive does not let a greedy gain rescue a failed uniform bar.

**What a fail means.** Under the failing offset model, two outside-uniform buried sites do not meet the proposed
quarter-budget tolerance on this case set. Do not transfer G107's unrestricted budget conclusion to that layout;
consider eight as the measured reference or test a different placement in a separate gate. A failed validity check
does not imply a placement failure.

**Not claimed.** No extension of G107's zero-sensor conclusion, universal two-sensor sufficiency, sensor/estimator
ranking outside this test, or within-block reconstruction fidelity. The ring is assumed, not a routed or measured
TSV/bond-pad design. No transient, area, supply, fault, or cost model; no claim about independent technology stacks.

## Lints checked: A1-A25

| Lint | What the design does |
|---|---|
| A1, A2 | Explicit arm and offset IDs, two nonzero buried budgets, and incomplete versus complete states; inventory sites against G107's dry controls and G104's mask. |
| A3, A22, A23 | Reuse G84's fingerprinted grid/splits and the source active-block map, in die/row/column order. No resampling; mask and readings use the same cell grid and existing temperature convention. |
| A4, A5 | Same case groups, top sites and test population throughout; keep site and chip identities through the ordered union, column lookup, and paired differences. |
| A6, A7, A9 | Use package placement, readings, score and metrics; import the two prior gates' public fit/grid/mask helpers rather than copy them. These are explicit dry-protocol dependencies, not new public package APIs; shared helpers should move into the package only if this becomes a recurrent pattern. |
| A8 | Setup, placement, scoring and output run from functions with explicit arguments; importing the script does not start a run. |
| A10, A11, A12 | Measure the one-chip slice first, then the five-chip dry; hidden Windows launcher with a deadline, peak cap and verified medium slot. Record process working set, not a machine-wide attribution. At this grid the existing dense eigensolve uses quadratic memory in the number of cells; greedy uses the fitted rank, and chips score serially without duplicating the fit. |
| A13, A18, A19, A21 | No offload, external service, converter, or new thermal solver; reuse G84's already built case set. This tests an estimator/placement comparison, not solver parity. |
| A14, A16, A17 | Separate slice/full records, refuse to overwrite complete or hash-mismatched results, atomically checkpoint each offset/chip unit, and resume only completed units after rechecking placement. A failed unit leaves the record incomplete, with prior units intact. Future gated evaluation must independently check completeness and validity. |
| A15, A20, A24 | No shared-code move/refactor, tool-limit raise, or new deployment bundle. Compare slice/full chip-1 outcomes; fit once and reuse the package's low-rank placement and scoring paths. |
| A25 | The dry numbers are cited to the dry JSON; statements about previous gates cite their records. |
