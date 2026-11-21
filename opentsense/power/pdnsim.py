"""OpenROAD PDNSim output files.

    voltages(path, worst) -> {instance: its worst terminal voltage}

The voltage file (`analyze_power_grid -voltage_file`) is CSV: Instance, Terminal, Layer, X location, Y location,
Voltage, one row per terminal. G97's evaluate.py carries its own copy of this reader (a frozen gate script).
"""


def voltages(path, worst):
    """{instance: its worst terminal voltage}: worst = min for a supply net (VDD), max for a ground net (VSS)."""
    v = {}
    with open(path) as fh:
        next(fh)
        for line in fh:
            if not line.strip():
                continue
            inst, _, _, _, _, volt = line.rstrip().rsplit(",", 5)   # from the right: an instance name may hold a comma
            x = float(volt)
            v[inst] = worst(v[inst], x) if inst in v else x
    return v
