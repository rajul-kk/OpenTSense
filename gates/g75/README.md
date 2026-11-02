# G75: shortcut errors re-measured

**Verdict: PASS (2 Nov 2026).** Registration, Amendments 1 and 2: `registration.md`. Numbers: `result.json`. Summary: `../../../gates.md`.

| Shortcut | Result |
|---|---|
| (1) Default vs real | IHP 1.732; cva6 2.14 (FF); ASAP7 ibex 3.02, TPU 1.63 |
| (2) Library vs SPICE | 0.893 to 4.233 at 25 °C, equal to G53; 0.06 to 0.49× at 75 to 100 °C |
| (3) Stack peak shift | 1.31 to 1.53 K, G71 3D stack in PACT |

The IHP and stack parts ran with `run.sh`; (2), cva6 and scoring ran with `resume.sh main spice cva6 score` in `opentsense:g75spice`. Lowest host free memory during cva6: 0.5 GB, with other apps open.
