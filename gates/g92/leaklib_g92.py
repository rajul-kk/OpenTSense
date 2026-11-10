"""Leakage-only Liberty generator: re-solve every leakage state of every cell in ngspice at several temperatures and
write one .lib per temperature, identical to the shipped file except the leakage values (G92).

A state with an internal value (Q of a flop or latch) is set by a capture sequence and then held; the state output
is measured at the end so a state that was not reached is detected, not silently mis-measured.

Usage (inside the OpenTSense image): leaklib.py <shipped .lib> <out dir> [jobs]
Writes <out dir>/leak_states.json and <out dir>/<lib stem>_<T>C.lib for T in TEMPS.
"""
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import subprocess
import tempfile

from opentsense.power.leak import SPICE

TEMPS = (25, 50, 75, 100, 125)
VDD = 1.2
CELLS_SPICE = f"{SPICE}/ihp/sg13g2_stdcell.spice"
OSDI = ("psp103", "psp103_nqs", "r3_cmc", "mosvar")
COMB, SEQ = (8, 7), (150, 140)            # tran end and measurement start, ns (as G53 / leak.py)


def ngspice(name, deck, osdi):
    """As leak.ngspice, but one solver thread per job: ngspice's default worker threads busy-wait, and many parallel
    jobs then starve each other (G92 Amendment 4). Results are unchanged."""
    with tempfile.TemporaryDirectory() as d:
        init = "set num_threads=1\n" + f"setcs sourcepath = ( $sourcepath {SPICE}/ihp/models {SPICE}/asap7 )\n" + "".join(f"osdi '{SPICE}/osdi/{m}.osdi'\n" for m in osdi)
        open(os.path.join(d, ".spiceinit"), "w").write(init)
        open(os.path.join(d, name + ".cir"), "w").write(deck)
        return subprocess.run(["ngspice", "-b", name + ".cir"], cwd=d, capture_output=True, text=True).stdout


def blocks(txt, head):
    """Yield (name, start, end) of every `head (name) {...}` group, end exclusive, brace-matched."""
    for m in re.finditer(head + r"\s*\(([^)]*)\)\s*\{", txt):
        depth, i = 1, m.end()
        while depth:
            c = txt[i]
            depth += (c == "{") - (c == "}")
            i += 1
        yield m.group(1).strip().strip('"'), m.start(), i


def literals(expr):
    """'!CLK&D' or '!A*!B' -> {'CLK': 0, 'D': 1}. Only products of literals are accepted."""
    if expr is None:
        return {}
    if re.search(r"[|+^()]", expr):
        raise ValueError(f"non-product when condition: {expr}")
    out = {}
    for t in re.split(r"[&*\s]+", expr.strip()):
        if t:
            out[t.lstrip("!")] = 0 if t.startswith("!") else 1
    return out


def minterms(expr, inputs):
    """A sum of products over the input pins -> its minterms, each as a product string. Each product's free inputs
    are enumerated, so every minterm is a full assignment; the state's leakage is then the mean over its minterms."""
    out = []
    for term in expr.split("+"):
        lit = literals(term)
        free = [p for p in inputs if p not in lit]
        for bits in range(2 ** len(free)):
            m = dict(lit, **{p: (bits >> i) & 1 for i, p in enumerate(free)})
            key = "&".join(("" if m[p] else "!") + p for p in sorted(m))
            if key not in out:
                out.append(key)
    return out


def parse_lib(txt):
    cells = {}
    for name, s, e in blocks(txt, r"\bcell"):
        body = txt[s:e]
        pins = {p: re.search(r'direction\s*:\s*"?(\w+)', txt[ps:pe]).group(1)
                for p, ps, pe in ((p, s + a, s + b) for p, a, b in blocks(body, r"\bpin")) if re.search(r"direction", txt[ps:pe])}
        states = []
        for _, a, b in blocks(body, r"\bleakage_power"):
            g = body[a:b]
            w = re.search(r'when\s*:\s*"([^"]*)"', g)
            states.append(dict(when=w.group(1) if w else None, lib_pW=float(re.search(r"value\s*:\s*([-+0-9.eE]+)", g).group(1))))
        cl = re.search(r"cell_leakage_power\s*:\s*([-+0-9.eE]+)", body)
        seq = None
        for kind in ("ff", "latch"):
            for _, a, b in blocks(body, r"\b" + kind):
                g = body[a:b]
                key = "clocked_on" if kind == "ff" else "enable"
                clk = re.search(key + r'\s*:\s*"([^"]*)"', g).group(1).strip()
                async_pins = {}                                  # pin -> level at which it forces the state
                for k in ("clear", "preset"):
                    m = re.search(k + r'\s*:\s*"([^"]*)"', g)
                    if m:
                        async_pins.update(literals(m.group(1)))
                seq = dict(kind=kind, clock=clk.lstrip("!"), active=0 if clk.startswith("!") else 1, async_pins=async_pins)
        cells[name] = dict(pins=pins, states=states, cell_leak_pW=float(cl.group(1)) if cl else None, seq=seq)
    return cells


def subckt_pins():
    out = {}
    for l in open(CELLS_SPICE):
        if l.lower().startswith(".subckt"):
            p = l.split()
            out[p[1]] = p[2:]
    return out


def pwl(points):
    return "PWL(" + " ".join(f"{t}n {v * VDD}" for t, v in points) + ")"


def deck(cell, info, order, state):
    """ngspice deck for one leakage state. Returns (deck text, state pin or None, expected state value)."""
    inputs = [p for p, d in info["pins"].items() if d == "input"]
    lit = literals(state["when"])
    statevars = [v for v in lit if v not in inputs]
    for v in statevars:
        if v not in info["pins"]:
            raise ValueError(f"{cell}: when names {v}, which is not a pin")
    if len(statevars) == 2 and sorted(v.endswith("_N") for v in statevars) == [False, True]:
        # Q and Q_N named together. Consistent: Q is set and checked. Equal (Q = Q_N, which the library lists for some
        # latches and flops): unreachable, so it takes the reachable state with the same Q, and is flagged.
        state["q_n_conflict"] = lit[statevars[0]] == lit[statevars[1]]
        statevars = [v for v in statevars if not v.endswith("_N")]
    if len(statevars) > 1:
        raise ValueError(f"{cell}: several state variables {statevars}")
    qpin = statevars[0] if statevars else None
    final = {p: lit.get(p, 0) for p in inputs}
    src = []
    seq = info["seq"]
    if qpin is None or seq is None:
        src = [f"V{p} n_{p} 0 {final[p] * VDD}" for p in inputs]
        te = COMB                                      # an output named in a combinational state is set by the inputs; still checked
    else:
        q = lit[qpin]
        clk, act = seq["clock"], seq["active"]
        async_on = [p for p, lv in seq["async_pins"].items() if final.get(p) == lv]
        te = SEQ
        if async_on:
            src = [f"V{p} n_{p} 0 {final[p] * VDD}" for p in inputs]       # the async input forces the state
        else:
            for p in inputs:
                if p == clk:
                    if seq["kind"] == "ff":
                        pts = [(0, 1 - act), (2, 1 - act), (2.05, act)] + ([] if final[p] == act else [(3, act), (3.05, 1 - act)])
                    else:
                        pts = [(0, 1 - act), (2, 1 - act), (2.05, act), (3, act), (3.05, 1 - act), (6, 1 - act), (6.05, final[p])]
                    src.append(f"V{p} n_{p} 0 {pwl(pts)}")
                elif p in seq["async_pins"]:
                    src.append(f"V{p} n_{p} 0 {final[p] * VDD}")
                else:
                    src.append(f"V{p} n_{p} 0 {pwl([(0, q), (5, q), (5.05, final[p])])}")
    nodes = ["VDD" if p == "VDD" else "0" if p == "VSS" else f"n_{p}" for p in order]
    ctl = "\n".join(f"option temp={t}\ntran 20p {te[0]}n\nmeas tran il{t} avg i(vdd) from={te[1]}n to={te[0]}n"
                    + (f"\nmeas tran vq{t} avg v(n_{qpin}) from={te[1]}n to={te[0]}n" if qpin else "") for t in TEMPS)
    d = (f"* {cell}\n.lib cornerMOSlv.lib mos_tt\n.include {CELLS_SPICE}\nVDD VDD 0 {VDD}\n" + "\n".join(src)
         + f"\nX1 {' '.join(nodes)} {cell}\n.control\n{ctl}\n.endc\n.end\n")
    return d, qpin, (lit[qpin] if qpin else None)


def solve(job):
    cell, k, d, qpin, q = job
    out = ngspice(f"{cell}_{k}", d, OSDI)
    il = {int(t): abs(float(x)) * VDD * 1e12 for t, x in re.findall(r"^il(\d+)\s*=\s*([-+0-9.eE]+)", out, re.M)}
    vq = {int(t): float(x) for t, x in re.findall(r"^vq(\d+)\s*=\s*([-+0-9.eE]+)", out, re.M)}
    ok = len(il) == len(TEMPS) and (qpin is None or (len(vq) == len(TEMPS) and all(abs(v - q * VDD) < 0.1 * VDD for v in vq.values())))
    return cell, k, dict(spice_pW=il, vq=vq or None, q_expect=q, ok=ok, **({} if ok else {"tail": out[-600:]}))


def write_lib(txt, cells, T):
    """Shipped text with every leakage value replaced by the SPICE value at T."""
    pieces, last = [], 0
    for name, s, e in blocks(txt, r"\bcell"):
        c = cells.get(name)
        body = txt[s:e]
        if c and c["solved"]:
            sts = iter(c["states"])

            def repl(m):
                st = next(sts)
                return re.sub(r"(value\s*:\s*)[-+0-9.eE]+", lambda v: f"{v.group(1)}{st['spice_pW'][T]:.6g}", m.group(0), count=1)
            body = re.sub(r"leakage_power\s*\(\s*\)\s*\{[^{}]*\}", repl, body)
            if c["cell_leak_pW"] is not None:
                body = re.sub(r"(cell_leakage_power\s*:\s*)[-+0-9.eE]+", lambda v: f"{v.group(1)}{c['cell_leak_new'][T]:.6g}", body, count=1)
        pieces += [txt[last:s], body]
        last = e
    return "".join(pieces + [txt[last:]])


def main(lib, out_dir, jobs=6):
    os.makedirs(out_dir, exist_ok=True)
    txt = open(lib).read()
    cells, order = parse_lib(txt), subckt_pins()
    work = []
    for name, c in cells.items():
        if name not in order:
            c["skip"] = "no SPICE subcircuit"
            continue
        sts = c["states"] or [dict(when=None, lib_pW=c["cell_leak_pW"] or 0.0, cell_only=True)]
        c["states"] = sts
        inputs = [p for p, d in c["pins"].items() if d == "input"]
        for k, st in enumerate(sts):
            if st["when"] and "+" in st["when"]:
                st["minterms"] = minterms(st["when"], inputs)
                for j, m in enumerate(st["minterms"]):
                    work.append((name, (k, j)) + deck(name, c, order[name], dict(st, when=m)))
            else:
                work.append((name, k) + deck(name, c, order[name], st))
    parts = {}
    with ThreadPoolExecutor(jobs) as ex:
        for name, k, r in ex.map(solve, work):
            if isinstance(k, tuple):
                parts.setdefault((name, k[0]), []).append(r)
            else:
                cells[name]["states"][k].update(r)
    for (name, k), rs in parts.items():                 # sum-of-products state: mean over its minterms
        ok = all(r["ok"] for r in rs)
        cells[name]["states"][k].update(ok=ok, q_expect=None, vq=None,
                                         spice_pW={T: sum(r["spice_pW"][T] for r in rs) / len(rs) for T in TEMPS} if ok else {},
                                         minterm_spice_pW=[r["spice_pW"] for r in rs])
    for name, c in cells.items():
        c["solved"] = "skip" not in c and all(s.get("ok") for s in c["states"])
        if c["solved"] and c["cell_leak_pW"] is not None:
            old = [s["lib_pW"] for s in c["states"]]
            c["cell_leak_new"] = {T: (c["cell_leak_pW"] * sum(s["spice_pW"][T] for s in c["states"]) / sum(old)) if sum(old) > 0
                                  else sum(s["spice_pW"][T] for s in c["states"]) / len(old) for T in TEMPS}
    stem = os.path.splitext(os.path.basename(lib))[0]
    for T in TEMPS:
        open(os.path.join(out_dir, f"{stem}_{T}C.lib"), "w").write(write_lib(txt, cells, T))
    json.dump(dict(lib=lib, temps=TEMPS, vdd=VDD, cells=cells), open(os.path.join(out_dir, "leak_states.json"), "w"), indent=1, default=str)
    n = sum(len(c["states"]) for c in cells.values() if "skip" not in c)
    bad = [(nm, k) for nm, c in cells.items() if "skip" not in c for k, s in enumerate(c["states"]) if not s.get("ok")]
    print(f"{len(cells)} cells, {n} states, {len(bad)} not ok, skipped: {[nm for nm, c in cells.items() if 'skip' in c]}")
    if bad:
        print("not ok:", bad[:20])
    return cells


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 6)
