"""Icarus-ready ASAP7 functional cell models, built from the pristine files shipped in the ORFS image.

The library models feed every flip-flop through `delayed_*` wires that only the specify block's timing checks
drive, so with the specify blocks gone (Icarus, zero delay) the core stays at X. The patch removes the specify
blocks and the `delayed_*` declarations and wires each `delayed_X` back to pin X. LVT and SLVT copies are the
same models with the cell suffix renamed (_R -> _L, _SL); they drop the UDP primitives, which the RVT files
already define.
Usage: python -m opentsense.power.asap7_models <pristine stdcell dir> <out dir> [R L SL]
"""
import glob
import os
import re
import shutil
import sys


def functional(text):
    text = re.sub(r"[ \t]*specify\b.*?\bendspecify\n", "", text, flags=re.S)
    text = re.sub(r"[ \t]*wire delayed_[^;]*;\n", "", text)
    return re.sub(r"\bdelayed_(\w+)", r"\1", text)


def build(src, out, vts=("R",)):
    """Writes the patched models for each threshold flavour in `vts`; returns the list of files for iverilog."""
    os.makedirs(out, exist_ok=True)
    files = []
    for f in sorted(glob.glob(os.path.join(src, "asap7sc7p5t_*.v"))):
        s = functional(open(f).read())
        base = os.path.basename(f)[:-2]
        for vt in vts:
            t = s if vt == "R" else re.sub(r"_ASAP7_75t_R\b", "_ASAP7_75t_" + vt,
                                          re.sub(r"\bprimitive\b.*?\bendprimitive\n", "", s, flags=re.S))
            p = os.path.join(out, base + ("" if vt == "R" else "_" + vt) + ".v")
            open(p, "w", newline="\n").write(t)
            files.append(p)
    # ORFS's empty.v gives the filler, tap and decap cells empty bodies
    shutil.copy(os.path.join(src, "empty.v"), out)
    return files + [os.path.join(out, "empty.v")]


if __name__ == "__main__":
    print("\n".join(build(sys.argv[1], sys.argv[2], tuple(sys.argv[3:]) or ("R",))))
