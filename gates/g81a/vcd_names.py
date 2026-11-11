"""G81a: make a Verilator VCD's net names match the netlist's escaped identifiers, as Icarus writes them.

Verilator writes an escaped identifier such as `\\alu_adder_result_ex[0] ` without its leading backslash, so OpenSTA reads
`alu_adder_result_ex[0]` as bit 0 of a bus that does not exist and leaves its pins unannotated. Only the header changes:
every $var whose name, with a backslash added, is an escaped identifier of the netlist gets the backslash back.
Value changes are copied unchanged. Usage: vcd_names.py <netlist.v> <in.vcd> <out.vcd>   Prints how many names changed."""
import sys

BS = chr(92)


def escaped(netlist):
    out = set()
    for tok in open(netlist).read().split():
        if tok.startswith(BS):
            out.add(tok[1:].rstrip(",;()"))
    return out


def main(netlist, src, dst):
    esc = escaped(netlist)
    n = 0
    with open(src, "rb") as f, open(dst, "wb") as g:
        for raw in f:
            if raw.startswith(b"$enddefinitions") or raw.lstrip().startswith(b"$enddefinitions"):
                g.write(raw)
                break
            t = raw.decode(errors="replace").split()
            if t and t[0] == "$scope" and len(t) >= 4 and BS in t[2] and BS + BS not in t[2]:
                # an instance name containing a backslash (e.g. the ALU's hierarchical Han-Carlson adder): Icarus writes
                # the backslash escaped (\\), Verilator plain; OpenSTA matches Icarus's form
                t[2] = t[2].replace(BS, BS + BS)
                raw = (" ".join(t) + "\n").encode()
                n += 1
            elif t and t[0] == "$var" and len(t) >= 6 and t[4] in esc:
                t[4] = BS + t[4]
                raw = (" ".join(t) + "\n").encode()
                n += 1
            g.write(raw)
        else:
            # no $enddefinitions: not a VCD header this script understands; refuse rather than copy it unchanged
            raise SystemExit(f"vcd_names: no $enddefinitions in {src}")
        while True:
            b = f.read(1 << 24)
            if not b:
                break
            g.write(b)
    print(f"{len(esc)} escaped identifiers in the netlist; {n} VCD names restored")


if __name__ == "__main__":
    main(*sys.argv[1:4])
