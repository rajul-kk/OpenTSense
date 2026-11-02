"""Convert the ASAP7 HSPICE model card and LVS CDL netlists to ngspice OSDI syntax. Usage: asap7_osdi.py <card> <cdl dir> <out dir>
BSIM-CMG 107 cards run on the 110 Verilog-A code (G41): coremod and capmod no longer exist and are dropped."""
import os
import re
import sys

CARD, CDL, OUT = sys.argv[1:4]
DROP = re.compile(r"\b(coremod|capmod|version)\s*=\s*\S+", re.I)


def card(text):
    out = []
    for line in text.splitlines():
        if line.lstrip().startswith("*"):
            continue
        m = re.match(r"\.model\s+(\S+)\s+([np])mos\s+level\s*=\s*72", line, re.I)
        if m:
            out.append(f".model {m[1]} bsimcmg devtype={1 if m[2].lower() == 'n' else 0}")
        elif line.startswith("+"):
            out.append(DROP.sub("", line))
    return "\n".join(out) + "\n"


def cells(text):
    out = []
    for line in text.splitlines():
        m = re.match(r"M(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+w=\S+\s+(.*)", line, re.I)
        out.append(f"N{m[1]} {m[2]} {m[3]} {m[4]} {m[5]} {m[6]} {m[7]}" if m else line)   # BSIM-CMG sets width from nfin
    return "\n".join(out) + "\n"


open(os.path.join(OUT, "asap7_tt_osdi.lib"), "w").write(card(open(CARD).read()))
for vt in ("R", "L", "SL"):
    open(os.path.join(OUT, f"cells_{vt}.sp"), "w").write(cells(open(os.path.join(CDL, f"asap7sc7p5t_28_{vt}.cdl")).read()))
