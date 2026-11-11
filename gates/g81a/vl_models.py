"""G81a: Verilator-compatible copy of the Icarus-ready ASAP7 RVT models used by G72 (G49's method): UDP primitives are
removed, and the cells that use them are replaced by zero-delay behavioural equivalents with the same function.
Usage: vl_models.py <G72 models dir> <netlist.v> <out.v>   Fails if a cell used by the netlist is missing."""
import glob
import os
import re
import sys

src, net, out = sys.argv[1:4]
BEH = {
    "DFFHQNx1_ASAP7_75t_R": "module DFFHQNx1_ASAP7_75t_R (QN, D, CLK); output reg QN; input D, CLK; always @(posedge CLK) QN <= ~D; endmodule",
    "DFFHQNx2_ASAP7_75t_R": "module DFFHQNx2_ASAP7_75t_R (QN, D, CLK); output reg QN; input D, CLK; always @(posedge CLK) QN <= ~D; endmodule",
    "DFFHQNx3_ASAP7_75t_R": "module DFFHQNx3_ASAP7_75t_R (QN, D, CLK); output reg QN; input D, CLK; always @(posedge CLK) QN <= ~D; endmodule",
    "DFFASRHQNx1_ASAP7_75t_R": ("module DFFASRHQNx1_ASAP7_75t_R (QN, D, RESETN, SETN, CLK); output reg QN; input D, RESETN, SETN, CLK;\n"
                                "  always @(posedge CLK or negedge RESETN or negedge SETN) if (!RESETN) QN <= 1'b1; else if (!SETN) QN <= 1'b0; else QN <= ~D;\nendmodule"),
    "DLLx1_ASAP7_75t_R": "module DLLx1_ASAP7_75t_R (Q, D, CLK); output reg Q; input D, CLK; always_latch if (!CLK) Q = D; endmodule",
    "DHLx1_ASAP7_75t_R": "module DHLx1_ASAP7_75t_R (Q, D, CLK); output reg Q; input D, CLK; always_latch if (CLK) Q = D; endmodule",
    "ICGx1_ASAP7_75t_R": ("module ICGx1_ASAP7_75t_R (GCLK, ENA, SE, CLK); output GCLK; input ENA, SE, CLK; reg en;\n"
                          "  always_latch if (!CLK) en = ENA | SE; assign GCLK = CLK & en;\nendmodule"),
}
mods, beh, dropped = {}, {}, []
for f in sorted(glob.glob(os.path.join(src, "asap7sc7p5t_*.v"))):
    s = re.sub(r"\bprimitive\b.*?\bendprimitive\b", "", open(f).read(), flags=re.S)
    for m in re.finditer(r"\bmodule\s+(\w+)\b.*?\bendmodule\b", s, flags=re.S):
        name = m.group(1)
        if name in mods or name in beh:
            continue
        if re.search(r"\baltos_\w+\s*\(", m.group(0)):      # uses a UDP: behavioural replacement if we have one
            if name in BEH:
                beh[name] = BEH[name]
            else:
                dropped.append(name)
            continue
        mods[name] = m.group(0)                             # G72's own model, unchanged
used = set(re.findall(r"^\s*(\w+_ASAP7_75t_R)\s+\w", open(net).read(), re.M))
missing = sorted(used - set(mods) - set(beh))
if missing:
    sys.exit(f"cells used by the netlist without a Verilator model: {missing}")
NL = chr(10)
open(out, "w", newline=NL).write((NL + NL).join(list(mods.values()) + [beh[n] for n in sorted(beh)]) + NL)
print(f"{len(mods)} cells kept, {len(beh)} behavioural {sorted(beh)}, {len(dropped)} UDP cells dropped, of which used: "
      f"{sorted(set(dropped) & used)}; netlist uses {len(used)} cell types")
