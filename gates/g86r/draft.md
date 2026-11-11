# G86r draft (9 Nov 2026): real-silicon sensor check on the laptop CPU · DRAFT, not registered; the user decides scope and bars

### G86r: Sparse-sensor recovery on a real die: Intel i7-1355U (RQ3; supports G86, G79, G88)
- **Why.** Every sensor in the testbed is simulated: noise σ = 0.65 or 1.34 K, assumed quantisation, no lag, no offsets. G86 needs real numbers for these, and G88 needs a plant identified from independent excitation. A real die gives both at no cost. It cannot test stacks: this is one flat die.
- **Hardware.** HP Pavilion x360 14-ek1xxx; Core i7-1355U (Raptor Lake-U), monolithic, 2 P-cores (4 threads) plus 8 E-cores (2 clusters of 4). Signals:
  - per-core digital thermal sensors (1 °C steps; how E-cores report within a cluster is to be checked in the dry run);
  - package temperature;
  - RAPL energy for the package and for the cores combined (no per-core power);
  - per-core busy and frequency from APERF/MPERF.
- **Tooling (choose one):**
  - **(A, preferred)** a Linux live USB with `turbostat --interval 0.05..1` and `stress-ng --taskset`. Free and scriptable. Needs a reboot into the stick.
  - **(B)** Windows with HWiNFO (free for personal use) CSV logging. No reboot, but a slower minimum interval and a kernel driver.
  - Docker and WSL cannot read the needed registers.
- **Protocol (proposal):**
  1. **Fixed conditions:** on mains power, one power profile, fan curve unchanged and recorded, 30 min idle before each session, room temperature noted.
  2. **Sensor characterisation:** 10 min all-idle and 10 min all-busy, giving per-sensor noise, quantisation, update interval, and the spread between cores at equilibrium (offsets are confounded with real gradients; report as an upper bound).
  3. **Identification runs:** pseudo-random binary load per core (one `stress-ng` worker pinned per core, independent on/off sequences, 1–30 s holds), 20 min, repeated with three seeds. Inputs are per-core busy × frequency (a power proxy) plus package RAPL; outputs are all core sensors.
  4. **Model:** a discrete linear model, N4SID or ARX, identified on seeds 1–2 and tested on seed 3.
  5. **Leave-one-sensor-out:** for each core, recover its temperature from the other sensors plus inputs with a Kalman filter on the identified model. Compare against (i) the mean of the other sensors and (ii) the identified model run open-loop without measurements.
- **Possible bars (for the user to fix before any data is taken):**
  - **(a)** the leave-one-out Kalman error is below both baselines for every core;
  - **(b)** the RMS error is under 1 K on the test seed;
  - **(c)** the measured sensor noise and quantisation fall inside G86's planned range; if they do not, G86's range is widened.
- **What it gives the thesis:**
  - real sensor statistics for G86;
  - a real identified-plant test for G79 and G88;
  - per-core busy and idle duration statistics from ordinary laptop use (a separate 1-hour log) as real schedule statistics for G81c's successor.
- **Limits:**
  - 2D only;
  - no dense ground truth (only the sensors themselves);
  - the firmware (power limits, turbo) changes frequency on its own; it is logged and treated as an input, not controlled;
  - a 15 W die has small gradients.
- **Plan check:** laptop only, no money. Option A needs the user to boot a live USB.
