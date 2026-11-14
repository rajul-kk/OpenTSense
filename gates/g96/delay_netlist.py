"""G96 route (b): a delay-annotated copy of a gate-level netlist, from OpenSTA's SDF.

The cell models stay zero-delay; delays are added around them, where they occur:
- each cell output is cut and driven through `assign #(rise, fall) net = cut;`, an inertial delay equal to the cell's
  fastest arc into that output (its shortest delay, which is also the narrowest pulse the cell passes);
- each cell input is cut and driven through a transport delay, `always @(net) cut <= #d net;`, where d is the wire
  delay from the net's driver to this pin plus how much slower this pin's arc is than the output's fastest arc.
So a path through input A to output Y takes wire(A) + arc(A->Y), each load keeps its own wire delay (clock skew
included), and only the cell's own delay filters pulses. A cell with several outputs (adders) is written once per
output, each copy driving one output with that output's input delays, so every arc is kept.

Approximations (stated in draft.md): rise and fall stay separate on outputs, input offsets use their mean; a pin pair
with several arcs (conditions, edges) uses its slowest; values are the max of each SDF min::max pair (one corner).
Times are ps; the SDF must say 1ps.

Usage: python gates/g96/delay_netlist.py <netlist.v> <design.sdf> <out.v>
Prints the counts; exits 1 if an SDF instance is missing from the netlist or an output in the netlist was not cut.
"""
import re
import sys
from collections import defaultdict

TRIPLE = r"\(([-\d.]*)::([-\d.]*)\)"
IOPATH = re.compile(rf"\(IOPATH\s+(\([^)]*\)|\S+)\s+(\S+)\s+{TRIPLE}\s+{TRIPLE}")
INTER = re.compile(rf"\(INTERCONNECT\s+(\S+)\s+(\S+)\s+{TRIPLE}\s+{TRIPLE}")
MODULE = re.compile(r"^module\s+(\\\S+|\w+)")
INST = re.compile(r"^\s*(\\\S+|\w+)\s+(\\\S+|\S+)\s*\(")
CELL = re.compile(r"^\s*(\w+_ASAP7_75t_\w+)\s+(\\\S+|\S+)\s*\(")
PORT = re.compile(r"\.(\w+)\(\s*(\\\S+ (?:\[\d+\])?|[^()\s]*)\s*\)")   # an escaped name may carry a bit-select


def raw(name):
    """SDF and Verilog escaped names -> the plain identifier both refer to."""
    return re.sub(r"\\(.)", r"\1", name).strip()


def big(m, first):
    """Max of the two min::max triples from group `first` on: (rise, fall)."""
    v = [float(x or 0) for x in m.group(first, first + 1, first + 2, first + 3)]
    return max(v[0], v[1]), max(v[2], v[3])


def read_sdf(path):
    """-> out {(inst, out pin): (rise, fall) of its fastest arc}, slow {(inst, in pin, out pin): ps}, wire {(inst, in pin): ps}."""
    arcs, wire, inst = defaultdict(dict), defaultdict(float), None
    with open(path) as fh:
        for line in fh:
            s = line.strip()
            if s.startswith("(TIMESCALE") and s.replace(" ", "") != "(TIMESCALE1ps)":
                raise SystemExit(f"SDF timescale must be 1ps: {s}")
            if s.startswith("(INSTANCE"):
                inst = raw(s[len("(INSTANCE"):].rstrip(")").strip()) or None
            elif (m := IOPATH.search(s)) and inst:
                src = raw(m.group(1).strip("()").split()[-1])     # "(posedge CLK)" -> CLK
                r, f = big(m, 3)
                old = arcs[(inst, m.group(2))].get(src, (0.0, 0.0))
                arcs[(inst, m.group(2))][src] = (max(old[0], r), max(old[1], f))   # slowest variant of a pin pair
            elif m := INTER.search(s):
                load = tuple(raw(m.group(2)).rsplit("/", 1))
                wire[load] = max(wire[load], *big(m, 3))
    out, slow = {}, {}
    for (i, o), a in arcs.items():
        r0, f0 = min(r for r, _ in a.values()), min(f for _, f in a.values())
        out[(i, o)] = (r0, f0)
        for src, (r, f) in a.items():
            slow[(i, src, o)] = (r - r0 + f - f0) / 2
    return out, slow, wire


class Writer:
    """Rewrites one module's cell instances; holds the declarations and delay statements they need."""

    def __init__(self, out, slow, wire):
        self.out, self.slow, self.wire = out, slow, wire
        self.decl, self.body, self.n_out, self.n_in = [], [], 0, 0

    def delayed_input(self, net, d):
        if d <= 0 or not net or net.startswith("1'b"):
            return net
        new, self.n_in = f"g96i_{self.n_in}", self.n_in + 1
        self.decl.append(f"  reg {new};\n")
        self.body.append(f"  initial {new} = {net};\n  always @({net}) {new} <= #{d:.4f} {net};\n")
        return new

    def cut_output(self, inst, pin, net):
        new, self.n_out = f"g96o_{self.n_out}", self.n_out + 1
        r, f = self.out[(inst, pin)]
        self.decl.append(f"  wire {new};\n")
        self.body.append(f"  assign #({r:.4f}, {f:.4f}) {net} = {new};\n")
        return new

    def instance(self, cell, name, inst, ports):
        """Lines for one cell instance: itself with delays, or one copy per output when it drives several."""
        # an escaped net ends at whitespace, so keep the space before any following token
        ports = [(p, n.strip() + " " if n.startswith("\\") else n.strip()) for p, n in ports]
        outs = [p for p, n in ports if (inst, p) in self.out and n]
        lines = []
        for o in outs if len(outs) > 1 else [outs[0] if outs else None]:
            conns = []
            for p, n in ports:
                if (inst, p) in self.out:
                    if o is None or p == o:
                        conns.append(f".{p}({self.cut_output(inst, p, n) if n else ''})")
                    continue
                d = self.wire.get((inst, p), 0.0) + self.slow.get((inst, p, o), 0.0)
                conns.append(f".{p}({self.delayed_input(n, d)})")
            copy = name if len(outs) <= 1 else (f"{name.strip()}_g96_{o} " if name.startswith("\\") else f"{name}_g96_{o}")
            lines.append(f" {cell} {copy} ({', '.join(conns)});\n")
        return lines


def annotate(netlist, out, slow, wire):
    """-> lines, Writer (its n_out, n_in), SDF instances not in the netlist, outputs named in the netlist but not cut."""
    with open(netlist) as fh:
        text = fh.readlines()
    mods = [raw(m.group(1)) for line in text if (m := MODULE.match(line))]
    inst_of = defaultdict(list)
    for line in text:
        if (m := INST.match(line)) and raw(m.group(1)) in mods[1:]:
            inst_of[raw(m.group(1))].append(raw(m.group(2)))
    for mod in mods[1:]:
        if len(inst_of[mod]) != 1:
            raise SystemExit(f"module {mod} is instantiated {len(inst_of[mod])} times; one SDF prefix per module expected")
    prefix = {mods[0]: "", **{mod: inst_of[mod][0] + "/" for mod in mods[1:]}}

    w, lines, present, uncut = Writer(out, slow, wire), [], set(), []
    mod_lines, block = None, None                       # open module's lines; open cell instance's lines
    for line in text:
        if m := MODULE.match(line):
            pre, mod_lines = prefix[raw(m.group(1))], []
        if block is None and CELL.match(line):
            block = []
        if block is not None:
            block.append(line)
            if not line.rstrip().endswith(");"):
                continue
            chunk, block = "".join(block), None
            cell, name = CELL.match(chunk).groups()
            inst, ports = pre + raw(name), PORT.findall(chunk)
            present.add(inst)
            # a pin named in the text but not parsed by PORT would silently keep zero delay
            parsed = {p for p, _ in ports}
            uncut += [(inst, p) for p in re.findall(r"\.(\w+)\(", chunk) if p not in parsed and (inst, p) in out]
            mod_lines.extend(w.instance(cell, name, inst, ports))
            continue
        if mod_lines is None:
            lines.append(line)
        elif line.startswith("endmodule"):
            head = next(k for k, x in enumerate(mod_lines) if x.rstrip().endswith(");")) + 1   # end of port list
            lines.extend(mod_lines[:head] + w.decl + mod_lines[head:] + w.body + [line])
            mod_lines, w.decl, w.body = None, [], []
        else:
            mod_lines.append(line)
    return lines, w, sorted({i for i, _ in out} - present), uncut


def main(netlist, sdf, dst):
    out, slow, wire = read_sdf(sdf)
    lines, w, missing, uncut = annotate(netlist, out, slow, wire)
    with open(dst, "w", newline="\n") as fh:
        fh.write("`timescale 1ps/1fs\n")
        fh.writelines(lines)
    print(f"outputs cut {w.n_out} (SDF outputs {len(out)}); inputs delayed {w.n_in}; "
          f"SDF instances not in the netlist {len(missing)} {missing[:3]}; outputs not parsed {len(uncut)} {uncut[:3]}")
    if missing or uncut:
        raise SystemExit(1)


if __name__ == "__main__":
    main(*sys.argv[1:4])
