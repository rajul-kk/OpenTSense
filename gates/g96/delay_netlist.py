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
       python gates/g96/delay_netlist.py view <out.v> <its vcd> <vcd for OpenSTA>   (see sta_view)
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


ASSIGN = re.compile(r"^\s*assign #\([^)]*\) (.+?) = (g96o_\d+);")


def sta_view(netlist, vcd_in, vcd_out):
    """The delay netlist's VCD as OpenSTA must read it. OpenSTA takes activity from the cell-instance scopes' pin
    variables, but here a cell's own output pin is the signal before its inertial delay, and a multi-output cell is
    split into copies. So: every output pin variable is pointed at the net it drives (after the delay; a bit of a
    vector net gets its own 1-bit variable), and the copies `<name>_g96_<pin>` are merged back under `<name>`.
    Value changes are copied unchanged. Returns (output pins re-pointed, of which vector bits, copies merged)."""
    target = {}                                          # g96o_k -> net name (raw) as the netlist assigns it
    with open(netlist) as fh:
        for line in fh:
            if m := ASSIGN.match(line):
                target[m.group(2)] = raw(m.group(1))
    with open(vcd_in) as src, open(vcd_out, "w", newline="\n") as out:
        head = []
        for line in src:
            head.append(line)
            if line.startswith("$enddefinitions"):
                break
        # header -> scope tree: [name, [var line parts], [children]]
        root, stack = ["", [], []], []
        stack.append(root)
        pre = []
        for line in head:
            p = line.split()
            if line.startswith("$scope"):
                node = [p[2], [], []]
                stack[-1][2].append(node)
                stack.append(node)
            elif line.startswith("$upscope"):
                stack.pop()
            elif line.startswith("$var"):
                stack[-1][1].append(p)
            elif not stack[1:] and not line.startswith("$enddefinitions"):
                pre.append(line)
        # in each scope: the net each g96o_k drives -> its id, or (vector id, bit position from the left)
        repoint, vec_bits, used, unresolved = {}, {}, set(), []
        n_new = 0

        def walk_ids(node):
            for v in node[1]:
                used.add(v[3])
            for c in node[2]:
                walk_ids(c)
        walk_ids(root)

        def resolve(node):
            nonlocal n_new
            names = {raw(v[4]): v for v in node[1]}
            for v in node[1]:
                if v[4] not in target:
                    continue
                net = target[v[4]]
                if net in names:
                    repoint[v[3]] = names[net][3]
                    continue
                m = re.fullmatch(r"(.+?) ?\[(\d+)\]", net)
                if not m or m.group(1) not in names:
                    unresolved.append(net)
                    continue
                base, bit = m.groups()
                vec = names[base]
                msb, lsb = (int(x) for x in vec[5].strip("[]").split(":"))
                pos = (msb - int(bit)) if msb >= lsb else (int(bit) - msb)
                new, n_new = f"g96v{n_new}", n_new + 1
                if new in used:
                    raise SystemExit(f"synthesised id {new} is already a VCD id")
                vec_bits.setdefault(vec[3], []).append((pos, int(vec[2]), new))
                repoint[v[3]] = new
            for c in node[2]:
                resolve(c)
        resolve(root)
        if unresolved:
            raise SystemExit(f"{len(unresolved)} driven nets not found in their VCD scope, e.g. {unresolved[:3]}")

        n_merged = 0

        def emit(node):
            nonlocal n_merged
            for v in node[1]:
                out.write(" ".join(v[:3] + [repoint.get(v[3], v[3])] + v[4:]) + "\n")
            merged = {}                                  # base name -> ({pin: var parts}, children)
            for c in node[2]:
                m = re.fullmatch(r"(.+)_g96_\w+", c[0])
                base = m.group(1) if m else c[0]
                n_merged += base in merged
                pins = merged.setdefault(base, ({}, c[2]))[0]
                for v in c[1]:
                    if v[3] in repoint:                  # an output re-pointed to its net wins over a copy's unconnected pin
                        pins[v[4]] = v
                    else:
                        pins.setdefault(v[4], v)
            for base, (pins, kids) in merged.items():
                out.write(f"$scope module {base} $end\n")
                emit([base, list(pins.values()), kids])
                out.write("$upscope $end\n")

        out.writelines(pre)
        for top in root[2]:
            out.write(f"$scope module {top[0]} $end\n")
            emit(top)
            out.write("$upscope $end\n")
        out.write("$enddefinitions $end\n")
        last = {}
        for line in src:
            out.write(line)
            if line[:1] in "bB":
                val, vid = line[1:].split()
                for pos, width, new in vec_bits.get(vid, ()):
                    full = val.rjust(width, val[0] if val[0] in "xXzZ" else "0")
                    if last.get(new) != full[pos]:
                        last[new] = full[pos]
                        out.write(f"{full[pos]}{new}\n")
    return len(repoint), sum(len(b) for b in vec_bits.values()), n_merged


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
    if sys.argv[1] == "view":            # python delay_netlist.py view <delay netlist> <vcd> <out vcd>
        print("output pins re-pointed %d (vector bits %d); copies merged %d" % sta_view(*sys.argv[2:5]))
    else:
        main(*sys.argv[1:4])
