# G106 draft: temperature sensors simulated as circuits (goal 18)

**Question.** G102's sensor profiles are datasheet classes, not circuits. What error does a sensor built from our own
cells give, after the trim a real chip gets, across process corners and supply, and does G102's ranking survive it?

## Method (dry, 17-18 Nov)

- `estimate.sensor_spice`: an 11-stage ring oscillator of minimum inverters (ASAP7 INVx1 RVT at 0.7 V, IHP
  sg13g2_inv_1 at 1.2 V), 1 fF per node (ASSUMED wiring), started from alternating node levels; the period is the
  mean of cycles 7-10 and must match cycles 4-7 to 0.2% (an all-low start ran a harmonic mode at 4x the frequency
  and was caught only at 125 C; code lint L55). And the IHP npn13G2 dVBE pair (ratio 8, 1 uA, ideal bias).
- `dry/sweep.py` (opentsense:g103, ngspice 45.2): 0-125 C (7 points), corners TT/SS/FF (G103's models), supply
  nominal x 0.95-1.05 (7 points); 45 decks, 16 s each on average (69 s worst, with other jobs running);
  `dry/sweep.json`. The key covers the image's model versions; a failed deck is retried, not stored.
- `dry/derive.py`: the reader knows the TT, nominal-supply curve and trims each chip once at 85 C (one-point ratio
  trim); error = reading - true temperature. For dVBE also a two-point trim at 0 and 125 C. `dry/derive.json`.
- The first sweep (`dry/sweep_v1.json`, `dry/derive_v1.json`, kept as run) gives the same corner errors.

## Dry results

| Sensor | Sensitivity at 85 C | Error after trim, SS / FF corner, worst over 0-125 C | Reading per mV of droop at 85 C | 1% droop, read back |
|---|---|---|---|---|
| ASAP7 ring | 0.055 %/K | -3.5 K (at 0 C) / +1.8 K (at 0 C) | +3.97 K (SS 4.11, FF 3.85) | +32 K (7 mV) |
| IHP ring | 0.030 %/K | -15.7 K (at 0 C) / +12.5 K (at 125 C) | +5.21 K (SS 5.83, FF 4.71) | +67 K (12 mV) |
| IHP dVBE pair | 0.196 mV/K (ideal kT/q ln 8: 0.179) | one-point trim 3.5 / 3.7 K (TT 3.6 K); two-point 0.6 K | bias not modelled | - |

Sign: a lower supply slows the ring, which reads hotter. The per-mV figure is the slope linearised at 85 C (the
period's change per mV over the sweep's +-1% points, which is close to linear, over the TT curve's slope at 85 C):
right for small squeezes. A large droop moves the reading up the TT curve, which flattens with temperature, so its
read-back grows faster than linear (1% droop: 4.6 K/mV for ASAP7, through the 25 K-step curve).

Seen:
- **On a shared core supply, the IR squeeze is the ring sensor's largest error at the worst tile.** G97 measured
  the TPU's tile squeeze (VDD drop plus VSS rise) at 0.58-0.92 mV mean and 4.70-5.02 mV worst
  (`gates/g97/README.md`, TPU part, windows W1-W3). At +3.97 K/mV that reads 2.3-3.7 K hot on average; at the
  worst tile 19-20 K by the linear slope and up to 23 K by the 1% read-back slope. Against the trimmed ASAP7 ring's
  corner error of at most 3.5 K and G102's whole `ring_osc` profile (1 K offset). On average the squeeze error is
  the same size as the corner error. Real designs regulate
  or ratio the sensor's supply for this reason; on a shared supply the reading follows the IR map.
- After a one-point trim, the ASAP7 ring's corner error is under 0.25 K within 75-100 C and grows towards the ends
  (SS -3.5 K at 0 C; FF +1.3 K at 125 C, +1.8 K at 0 C): up to three and a half times G102's 1 K `ring_osc`
  offset, so the datasheet class was optimistic away from the trim point. The IHP ring at 1.2 V is a poor
  thermometer (0.03 %/K, corner errors up to 16 K): its delay is near the temperature-insensitive point at that
  supply.
- The dVBE pair's error is nearly the same at every corner (a ratio is insensitive to process). With one trim it
  is a slope error of up to 3.7 K; a two-point trim leaves 0.6 K, the curvature of the device's dVBE(T).

## Proposed gate (for the student)

Rerun G102's harness (G84's case set and sites, chips 21-30, salt 106) with an `asap7_ring` profile built from
`derive.json` (corner drawn per chip from TT/SS/FF, its trimmed error curve as a systematic term, G102's noise and
quantisation), in two supply cases:
- **regulated**: no supply term;
- **core supply**: each sensor's period scaled by the swept supply response at its squeeze (`sweep.json`, the
  corner's curve interpolated in supply) and read back through the trimmed TT curve, so it reads **hotter**. The
  squeeze at a site is G97's tile squeeze there (top die: the TPU window of the case, W1-W3, G97's maps resampled
  onto G84's 1 mm block; bottom die: G97's Ibex k0-k4 mean map; sites outside the block: no squeeze).
Bars: (a) regulated, field model beats the average (CI below 0) in >= 8 of 10 chips, both dies; (b) core supply,
reported, with the same test. Student decisions first: which supply case is the realistic one for this benchmark,
and whether the dVBE profile takes the one-point (3.7 K) or two-point (0.6 K) trim.

## Lints checked

| Lint | What the design does |
|---|---|
| A6 package logic | decks and parsing in `estimate.sensor_spice`, reusing `power.leak.ngspice` and its abort patterns |
| A9 one source | nominal supplies, the dVBE ratio and the corners come from `sensor_spice` and `power.leak`, not copies |
| A10 cost | measured: 16 s per deck on average, 45 decks |
| A16 per unit | one deck per (kit, corner, supply); a failed deck is reported alone and retried on the next run (L54) |
| A17 resume | `sweep.json` is written after each unit; the key hashes the code, the image tag and its model versions |
| A19 tool quirks | ngspice: `uic` start state, two-window periodicity check (L55); IHP HBT is a subcircuit with its own corner libs |
| A21 independent reference | dVBE against the ideal kT/q ln 8 line |
| A25 citations | numbers above from `dry/derive.json` and `dry/sweep.json`; G97 squeeze from `gates/g97/README.md` |
| not applicable | A1-A5, A11-A13, A18, A20, A22-A24 |
