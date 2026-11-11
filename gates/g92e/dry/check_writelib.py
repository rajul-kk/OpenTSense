"""G92e dry check (not scored): the refactored write_lib (cell status) reproduces G92d's written libraries byte for byte
from G92d's own leak_states.json. Usage: check_writelib.py <g92d run kit dir>..."""
import glob
import json
import os
import re
import sys

from opentsense.power import leaklib as L

for R in sys.argv[1:]:
    J = json.load(open(f"{R}/lib/leak_states.json"))
    cells = J["cells"]
    for c in cells.values():
        c["status"] = L.SKIPPED if "skip" in c else L.CELL_SOLVED if c.get("solved") else L.KEPT_SHIPPED
        for s in c["states"]:
            if s.get("spice_pW"):
                s["spice_pW"] = {int(t): x for t, x in s["spice_pW"].items()}
        if c.get("cell_leak_new"):
            c["cell_leak_new"] = {int(t): x for t, x in c["cell_leak_new"].items()}
    n = bad = 0
    for lib in J["libs"]:
        txt = L.read(lib)
        stem = re.sub(r"\.lib(\.gz)?$", "", os.path.basename(lib))
        mine = {k: c for k, c in cells.items() if c["lib"] == os.path.basename(lib)}
        for T in L.TEMPS:
            ref = open(f"{R}/lib/{stem}_{T}C.lib").read()
            n += 1
            bad += L.write_lib(txt, mine, T) != ref
    print(R, f"{n} libs, {bad} differ, kept_shipped={sorted(k for k, c in cells.items() if c['status'] == L.KEPT_SHIPPED)}")
