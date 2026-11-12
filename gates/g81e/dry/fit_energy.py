"""G81e dry check (not scored): fit the per-window energy model to DRAMPower and test it on held-out traces.

Calibration traces: read-only, write-only, idle (refresh only) and one mixed. Held out: five mixed H1 traces with other
seeds, bank-hash salts and refresh phases. For each held-out trace, DRAMPower's total and per-bank energies are
compared with the model's prediction. Runs DRAMPower 6.3.1 in WSL (G50a's install and memspec).

Usage (from the opentsense repo root): python gates/g81e/dry/fit_energy.py gates/g81e/dry/fit_energy.json
"""
import json
import subprocess
import sys

import numpy as np

sys.path.insert(0, ".")
from opentsense.power import cache, dramctl, dramenergy  # noqa: E402

MS = "/home/rajul/tools/DRAMSys/configs/memspec/JEDEC_8Gb_LPDDR4-3200_16bit.json"
NB = dramctl.LPDDR4_3200["arch"]["nbrOfBanks"]
CFG = json.dumps({"useToggleRate": False, "simconfig": {}})


def drampower(tr):
    subprocess.run(["wsl", "-e", "bash", "-c", "mkdir -p ~/g81e_dry && cat > ~/g81e_dry/trace.csv"], input=tr.csv(),
                   text=True, check=True)
    subprocess.run(["wsl", "-e", "bash", "-c", "cat > ~/g81e_dry/cfg.json"], input=CFG, text=True, check=True)
    r = subprocess.run(["wsl", "-e", "bash", "-c", f"cd ~/g81e_dry && ~/tools/DRAMPower/build/bin/cli -c cfg.json "
                        f"-t trace.csv -m {MS} -j out.json >/dev/null && cat out.json"], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-1000:])
    return json.loads(r.stdout)


def traffic(seed, n, cycles, wfrac, dfrac=0.5, salt=None, phase=0):
    rng = np.random.default_rng(seed)
    cyc = np.sort(rng.integers(0, cycles, n))
    port = np.where(rng.random(n) < dfrac, "D", "I")
    addr = np.where(port == "I", rng.integers(0, 1 << 15, n), rng.integers(1 << 20, (1 << 20) + (1 << 18), n)) & ~3
    we = (port == "D") & (rng.random(n) < wfrac)
    tr = dramctl.schedule(cache.h1(cyc, port, we, addr).txn, bank_salt=salt, ref_phase=phase, end_cycle=cycles)
    assert dramctl.check(tr) == []
    return tr


def main(out_path):
    cal = [traffic(1, 20000, 2_000_000, 0.0, dfrac=1.0),          # data reads only
           traffic(2, 20000, 2_000_000, 1.0, dfrac=1.0),          # data writes (plus their fills)
           dramctl.schedule(cache.Txn(*(np.zeros(0, t) for t in (np.int64, np.int64, bool, np.int64))),
                            end_cycle=2_000_000),                 # refresh only
           traffic(3, 20000, 2_000_000, 0.3)]
    model, resid = dramenergy.fit([(t, drampower(t)) for t in cal], NB)
    held = []
    for seed in range(10, 15):
        tr = traffic(seed, int(np.random.default_rng(seed).integers(5000, 40000)), 2_000_000, 0.3,
                     salt=seed, phase=seed * 997 % dramctl.LPDDR4_3200["t"]["REFI"])
        o = drampower(tr)
        p = dramenergy.predict_totals(tr, NB, model)
        banks = o["CoreEnergy"]["BankEnergy"]
        core = np.array([sum(b[k] for k in dramenergy.PER_BANK) for b in banks])
        io = o["InterfaceEnergy"]["controller"]["dynamicEnergy"] + o["InterfaceEnergy"]["dram"]["dynamicEnergy"]
        static = o["InterfaceEnergy"]["controller"]["staticEnergy"] + o["InterfaceEnergy"]["dram"]["staticEnergy"]
        held.append({"seed": seed, "total_drampower_J": o["TotalEnergy"], "total_model_J": p["total"],
                     "total_rel_err": abs(p["total"] - o["TotalEnergy"]) / o["TotalEnergy"],
                     "bank_core_max_rel_err": float(np.max(np.abs(p["bank_core"] - core) / core)),
                     "bg_act_rel_err": abs(p["bg_act"] - o["CoreEnergy"]["E_bg_act_shared"]) / o["CoreEnergy"]["E_bg_act_shared"],
                     "io_rel_err": abs(p["io"] - io) / io, "unmodelled_static_share": static / o["TotalEnergy"]})
    res = {"model": model.as_dict(), "fit_max_rel_residual": resid, "held_out": held,
           "held_out_worst_total_rel_err": max(h["total_rel_err"] for h in held),
           "held_out_worst_bank_rel_err": max(h["bank_core_max_rel_err"] for h in held)}
    json.dump(res, open(out_path, "w"), indent=1)
    print(json.dumps({k: res[k] for k in ("fit_max_rel_residual", "held_out_worst_total_rel_err",
                                          "held_out_worst_bank_rel_err")}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
