"""Leakage-only Liberty generator: re-solve every leakage state of every cell in ngspice at several temperatures and
write one .lib per temperature, identical to the shipped file except the leakage values (G92, generalised in G92b).

Each state is planned from the cell's own Liberty logic before any SPICE run:
- its input levels are the pins it names (unnamed inputs are held low);
- a cell with an ff, latch or clock-gate statetable has one stored value s; the state's named outputs, evaluated with the
  output functions, say which s it needs, and an active clear/preset or an open latch forces s;
- a state that no s satisfies, or whose s contradicts a forced s, cannot be held by the circuit. It is classed
  `unreachable`, and takes the leakage of the state the circuit does hold at the same inputs (G92b registration);
- a state that leaves s free (outputs do not depend on it) is solved at s = 0 and s = 1 and averaged (`free`);
- a sum-of-products state is expanded into its minterms over the pins it names; its value is the mean over the
  reachable minterms.
s is set by a capture sequence, then held. Every output pin is measured over the window and checked against the
planned level within 10% of VDD, so a state that was not reached is detected, not mis-measured.

Usage (inside the OpenTSense image): leaklib.py <kit> <out dir> <jobs> <shipped .lib[.gz]> [more libs...]
Writes <out dir>/leak_states.json and <out dir>/<lib stem>_<T>C.lib for every lib and T in TEMPS.
"""
import gzip
import itertools
import json
import os
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

from opentsense.power.leak import SPICE

TEMPS = (25, 50, 75, 100, 125)
KITS = {
    "ihp": dict(vdd=1.2, cells=f"{SPICE}/ihp/sg13g2_stdcell.spice", osdi=("psp103", "psp103_nqs", "r3_cmc", "mosvar"),
                models=".lib cornerMOSlv.lib mos_tt\n.lib cornerDIO.lib dio_tt"),
    "asap7": dict(vdd=0.7, cells=f"{SPICE}/asap7/cells_R.sp", osdi=("bsimcmg",), models=f".include {SPICE}/asap7/asap7_tt_osdi.lib\n.options cshunt=1e-14"),
    # node shunt: no DC current; lets the transient pass clock edges. 1 fF in G92b; 10 fF in G92c, where 1 fF still let 24 states
    # (large clock gates, SDFHx4/SDFLx4, some latches) stop. G92c showed the shunt does move constant-input states by 0.1-1% at
    # 25 C (deep stacks: the 25 C solve is ill-conditioned), so it is kept at 10 fF and G92d's regression is against G92c.
}
KITS["asap7_lvt"] = dict(KITS["asap7"], cells=f"{SPICE}/asap7/cells_L.sp")      # G92c: the same kit with LVT cells
COMB, SEQ = (8, 7), (150, 140)            # tran end and measurement start, ns (as G53 / leak.py)
EDGE = 0.05                               # input edge time in capture sequences, ns (G92/G92b value)
SETTLE = True                             # captured states are settled (G92c: DC seeded from a continuation; G92d: staged continuation)


def ngspice(name, deck, osdi, keep=()):
    """As leak.ngspice, but one solver thread per job: ngspice's default worker threads busy-wait, and many parallel
    jobs then starve each other (G92 Amendment 4). Results are unchanged. `keep`: files the run writes, returned as bytes."""
    with tempfile.TemporaryDirectory() as d:
        init = "set num_threads=1\n" + f"setcs sourcepath = ( $sourcepath {SPICE}/ihp/models {SPICE}/asap7 )\n" + "".join(f"osdi '{SPICE}/osdi/{m}.osdi'\n" for m in osdi)
        open(os.path.join(d, ".spiceinit"), "w").write(init)
        open(os.path.join(d, name + ".cir"), "w").write(deck)
        out = subprocess.run(["ngspice", "-b", name + ".cir"], cwd=d, capture_output=True, text=True).stdout
        if not keep:
            return out
        return out, {f: open(os.path.join(d, f), "rb").read() for f in keep if os.path.exists(os.path.join(d, f))}


def raw_last(b):
    """Binary ngspice raw file -> {vector name: value at the last time point}."""
    i = b.index(b"Binary:\n")
    head = b[:i].decode(errors="replace").splitlines()
    nv = int(next(l for l in head if l.startswith("No. Variables:")).split(":")[1])
    npt = int(next(l for l in head if l.startswith("No. Points:")).split(":")[1])
    k = next(j for j, l in enumerate(head) if l.startswith("Variables:"))
    names_ = [head[k + 1 + j].split()[1] for j in range(nv)]
    import struct
    row = struct.unpack(f"<{nv}d", b[i + 8 + (npt - 1) * nv * 8: i + 8 + npt * nv * 8])
    return dict(zip(names_, row))


# ---------------- Liberty boolean expressions ----------------
TOK = re.compile(r"\s*([A-Za-z_][\w\[\]]*|[01]|[!'&*|+^()]|\s)")


def _tokens(expr):
    out, i = [], 0
    expr = expr.strip()
    while i < len(expr):
        if expr[i].isspace():
            j = i
            while j < len(expr) and expr[j].isspace():
                j += 1
            out.append(" ")
            i = j
            continue
        m = re.match(r"[A-Za-z_][\w\[\]]*|[01]|[!'&*|+^()]", expr[i:])
        if not m:
            raise ValueError(f"bad token in {expr!r}")
        out.append(m.group(0))
        i += len(m.group(0))
    # a space is AND only between two operands
    clean = []
    for k, t in enumerate(out):
        if t == " ":
            prev = clean[-1] if clean else None
            nxt = next((u for u in out[k + 1:] if u != " "), None)
            if prev is not None and nxt is not None and (prev not in "!&*|+^(" ) and (nxt not in "&*|+^)'"):
                clean.append("&")
            continue
        clean.append(t)
    return clean


def evaluate(expr, env):
    """Liberty boolean expression -> 0/1. Precedence: OR (| +) < XOR (^) < AND (& * space) < NOT (! prefix, ' postfix)."""
    t = _tokens(expr)
    pos = [0]

    def peek():
        return t[pos[0]] if pos[0] < len(t) else None

    def take():
        pos[0] += 1
        return t[pos[0] - 1]

    def p_or():
        v = p_xor()
        while peek() in ("|", "+"):
            take(); v = v | p_xor()
        return v

    def p_xor():
        v = p_and()
        while peek() == "^":
            take(); v = v ^ p_and()
        return v

    def p_and():
        v = p_not()
        while peek() in ("&", "*"):
            take(); v = v & p_not()
        return v

    def p_not():
        if peek() == "!":
            take(); v = 1 - p_not()
        else:
            v = p_atom()
        while peek() == "'":
            take(); v = 1 - v
        return v

    def p_atom():
        x = take()
        if x == "(":
            v = p_or()
            assert take() == ")", expr
            return v
        if x in ("0", "1"):
            return int(x)
        if x not in env:
            raise KeyError(f"{x} in {expr!r}")
        return env[x]

    v = p_or()
    assert pos[0] == len(t), expr
    return v


def names(expr):
    return sorted({x for x in _tokens(expr) if re.match(r"[A-Za-z_]", x)})


def literals(expr):
    """'!CLK&D', '!A*!B' or '(A * !B)' -> {'CLK': 0, 'D': 1}. Only products of literals are accepted."""
    if expr is None:
        return {}
    e = expr.replace("(", " ").replace(")", " ") if not re.search(r"!\s*\(", expr) else expr
    if re.search(r"[|+^()']", e):
        raise ValueError(f"non-product when condition: {expr}")
    out = {}
    for tkn in re.split(r"[&*\s]+", e.strip()):
        if tkn:
            out[tkn.lstrip("!")] = 0 if tkn.startswith("!") else 1
    return out


def is_product(expr):
    try:
        literals(expr)
        return True
    except ValueError:
        return False


def minterms(expr, pins=None):
    """Any expression -> its satisfying full assignments over the pins it names (each a product string), in a fixed order."""
    vs = names(expr) if pins is None else pins
    out = []
    for bits in itertools.product((0, 1), repeat=len(vs)):
        env = dict(zip(vs, bits))
        if evaluate(expr, env):
            out.append("&".join(("" if env[p] else "!") + p for p in vs))
    return out


# ---------------- Liberty parsing ----------------
def blocks(txt, head):
    """Yield (name, start, end) of every `head (name) {...}` group, end exclusive, brace-matched."""
    for m in re.finditer(head + r"\s*\(([^)]*)\)\s*\{", txt):
        depth, i = 1, m.end()
        while depth:
            c = txt[i]
            depth += (c == "{") - (c == "}")
            i += 1
        yield m.group(1).strip().strip('"'), m.start(), i


def attr(g, key):
    m = re.search(r"\b" + key + r'\s*:\s*"?([^";\n]*?)"?\s*;', g)
    return m.group(1).strip() if m else None


def leak_groups(body):
    """(start, end, when, value, pg) of every leakage_power group in a cell body, in order."""
    out = []
    for _, a, b in blocks(body, r"\bleakage_power"):
        g = body[a:b]
        w = re.search(r'when\s*:\s*"([^"]*)"', g)
        out.append((a, b, w.group(1) if w else None, float(re.search(r"value\s*:\s*([-+0-9.eE]+)", g).group(1)), attr(g, "related_pg_pin")))
    return out


def parse_lib(txt):
    cells = {}
    for name, s, e in blocks(txt, r"\bcell"):
        body = txt[s:e]
        for _, a, b in sorted(blocks(body, r"\btest_cell"), key=lambda x: -x[1]):   # a scan cell's test_cell holds its non-scan model
            body = body[:a] + body[b:]
        pins, funcs, cg, tri = {}, {}, {}, {}
        for p, a, b in blocks(body, r"\bpin"):
            g = body[a:b]
            d = attr(g, "direction")
            if d is None:
                continue
            pins[p] = d
            f = attr(g, "function") or attr(g, "state_function")
            if f and d in ("output", "inout"):
                funcs[p] = f
            if attr(g, "three_state"):
                tri[p] = attr(g, "three_state")
            for role in ("clock", "enable", "test"):
                if re.search(rf"clock_gate_{role}_pin\s*:\s*true", g):
                    cg[role] = cg.get(role, []) + [p]
        states = [dict(when=w, lib_pW=v) for a, b, w, v, pg in leak_groups(body) if pg != "VSS"]
        cl = re.search(r"cell_leakage_power\s*:\s*([-+0-9.eE]+)", body)
        seq = None
        for kind in ("ff", "latch"):
            for vars_, a, b in blocks(body, r"\b" + kind):
                g = body[a:b]
                v1, v2 = [v.strip().strip('"') for v in vars_.split(",")]
                clk = attr(g, "clocked_on" if kind == "ff" else "enable")
                lc = literals(clk)
                assert len(lc) == 1, (name, clk)
                (ck, act), = lc.items()
                seq = dict(kind=kind, var1=v1, var2=v2, clock=ck, active=act, data=attr(g, "next_state" if kind == "ff" else "data_in"),
                           clear=attr(g, "clear"), preset=attr(g, "preset"), cpv1=attr(g, "clear_preset_var1"), cpv2=attr(g, "clear_preset_var2"))
        if seq is None and "statetable" in body:
            # integrated clock gate (latch_posedge[_precontrol]): a latch open while CLK is low, data = enable | test
            kindcg = attr(body, "clock_gating_integrated_cell")
            inode = re.search(r'internal_node\s*:\s*"?(\w+)', body).group(1)
            assert kindcg and kindcg.startswith("latch_posedge") and len(cg.get("clock", [])) == 1, (name, kindcg, cg)
            seq = dict(kind="latch", var1=inode, var2=None, clock=cg["clock"][0], active=0, data=" | ".join(cg.get("enable", []) + cg.get("test", [])),
                       clear=None, preset=None, cpv1=None, cpv2=None, clock_gate=kindcg)
        cells[name] = dict(pins=pins, funcs=funcs, states=states, cell_leak_pW=float(cl.group(1)) if cl else None, seq=seq, tri=tri)
    return cells


def subckt_pins(path):
    out = {}
    for l in open(path):
        if l.lower().startswith(".subckt"):
            p = l.split()
            out[p[1]] = p[2:]
    return out


# ---------------- state planning ----------------
def _env(seq, s):
    return {seq["var1"]: s, **({seq["var2"]: 1 - s} if seq["var2"] else {})}


def _closest(F, free, want):
    """Assignment of the pins in `free` closest (Hamming) to F that makes want(env) true, or None."""
    best = None
    for bits in itertools.product((0, 1), repeat=len(free)):
        env = dict(F, **dict(zip(free, bits)))
        if want(env):
            d = sum(env[p] != F[p] for p in free)
            if best is None or d < best[0]:
                best = (d, env)
    return best and best[1]


def plan(cell, info, when):
    """One product state -> list of solve plans (1, or 2 if the stored value is free) and flags.
    A plan: dict(F=input levels, s=stored value or None, forced=bool, expect={out pin: level}, ic={inout pin: level}).
    G92c: an output whose three_state expression is true at F is high-impedance. It has no planned level, is left
    floating (the isolated cell's own DC level), and is not checked; the plan is flagged `hiz`."""
    ps, flags = _plan(cell, info, when)
    tri = info.get("tri", {})
    for p in ps:
        off = [q for q, e in tri.items() if q in p["expect"] and evaluate(e, p["F"])]
        for q in off:
            p["expect"].pop(q)
        if off:
            flags["hiz"] = True
    return ps, flags


def _plan(cell, info, when):
    pins, funcs, seq = info["pins"], info["funcs"], info["seq"]
    lit = literals(when)
    for v in lit:
        if v not in pins:
            raise ValueError(f"{cell}: when names {v}, which is not a pin")
    inputs = [p for p, d in pins.items() if d == "input"]
    F = {p: lit.get(p, 0) for p in inputs}
    named_out = {p: v for p, v in lit.items() if pins[p] == "output"}
    ic = {p: v for p, v in lit.items() if pins[p] == "inout" and p not in funcs}
    outs = [p for p in funcs if pins[p] == "output"]
    flags = {}
    if seq is None:
        expect = {p: evaluate(funcs[p], F) for p in outs}
        flags["unreachable"] = any(expect[p] != v for p, v in named_out.items())
        return [dict(F=F, s=None, forced=True, expect=expect, ic=ic)], flags
    forced_env = None
    clr = evaluate(seq["clear"], F) if seq["clear"] else 0
    pre = evaluate(seq["preset"], F) if seq["preset"] else 0
    if clr and pre:
        cv = {"L": 0, "H": 1}
        forced_env = {seq["var1"]: cv[seq["cpv1"]], **({seq["var2"]: cv[seq["cpv2"]]} if seq["var2"] else {})}
    elif clr or pre:
        forced_env = _env(seq, 0 if clr else 1)
    elif seq["kind"] == "latch" and F[seq["clock"]] == seq["active"]:
        forced_env = _env(seq, evaluate(seq["data"], F))
    out_at = lambda env: {p: evaluate(funcs[p], dict(F, **env)) for p in outs}
    if forced_env is not None:
        expect = out_at(forced_env)
        flags["unreachable"] = any(expect[p] != v for p, v in named_out.items())
        return [dict(F=F, s=forced_env[seq["var1"]], forced=True, expect=expect, ic=ic)], flags
    C = [s for s in (0, 1) if all(out_at(_env(seq, s))[p] == v for p, v in named_out.items())]
    if len(C) == 1:
        ss = C
    elif not C:
        # no stored value gives the named outputs (e.g. Q = Q_N): take s from the first named output that depends on s
        flags["unreachable"] = True
        dep = [p for p in named_out if out_at(_env(seq, 0))[p] != out_at(_env(seq, 1))[p]]
        ss = [next(s for s in (0, 1) if out_at(_env(seq, s))[dep[0]] == named_out[dep[0]])]
    else:
        flags["free"] = True
        ss = [0, 1]
    return [dict(F=F, s=s, forced=False, expect=out_at(_env(seq, s)), ic=ic) for s in ss], flags


def pwl(points, vdd):
    return "PWL(" + " ".join(f"{t}n {v * vdd}" for t, v in points) + ")"


def deck(cell, info, order, p, kit):
    """ngspice deck for one plan."""
    K = KITS[kit]
    vdd = K["vdd"]
    seq, F = info["seq"], p["F"]
    inputs = list(F)
    src = []
    te = SEQ if seq else COMB
    if p["forced"] or seq is None:
        src = [f"V{q} n_{q} 0 {F[q] * vdd}" for q in inputs]
    else:
        clk, act, s = seq["clock"], seq["active"], p["s"]
        asyn = sorted(set((names(seq["clear"]) if seq["clear"] else []) + (names(seq["preset"]) if seq["preset"] else [])) - {clk})
        hold = _closest(F, asyn, lambda e: not ((seq["clear"] and evaluate(seq["clear"], e)) or (seq["preset"] and evaluate(seq["preset"], e)))) if asyn else dict(F)
        dpins = [q for q in names(seq["data"]) if q in F and q != clk and q not in asyn]
        cap = _closest(hold, dpins, lambda e: evaluate(seq["data"], e) == s)
        if cap is None:
            raise ValueError(f"{cell}: no data input sets {seq['var1']} = {s}")
        E = EDGE
        for q in inputs:
            if q == clk:
                if seq["kind"] == "ff":
                    pts = [(0, 1 - act), (2, 1 - act), (2 + E, act)] + ([] if F[q] == act else [(3, act), (3 + E, 1 - act)])
                else:
                    pts = [(0, 1 - act), (2, 1 - act), (2 + E, act), (3, act), (3 + E, 1 - act), (6, 1 - act), (6 + E, F[q])]
                src.append(f"V{q} n_{q} 0 {pwl(pts, vdd)}")
            else:
                src.append(f"V{q} n_{q} 0 {pwl([(0, cap[q]), (5, cap[q]), (5 + E, F[q])], vdd)}")
    nodes = ["VDD" if q == "VDD" else "0" if q in ("VSS", "GND") else f"n_{q}" for q in order]
    chk = list(p["expect"]) + list(p["ic"])
    passive = not info["funcs"] and not p["ic"]          # no output (antenna diode): leakage is the power all sources deliver
    meas = ["set filetype=binary"] if is_capture(info, p) else []
    for t in TEMPS:
        meas += [f"option temp={t}", f"tran 20p {te[0]}n", f"meas tran il{t} avg i(vdd) from={te[1]}n to={te[0]}n"]
        if is_capture(info, p):
            meas += [f"write r{t}.raw"]
        meas += [f"meas tran v_{q}_{t} avg v(n_{q}) from={te[1]}n to={te[0]}n" for q in chk]
        if passive:
            meas += [f"meas tran ii_{q}_{t} avg i(v{q}) from={te[1]}n to={te[0]}n" for q in inputs]
    ics = (".ic " + " ".join(f"v(n_{q})={v * vdd}" for q, v in p["ic"].items()) + "\n") if p["ic"] else ""
    if (p["forced"] or seq is None) and p["expect"]:
        # constant inputs: start the solver at the planned output levels; BSIM-CMG otherwise finds a spurious operating point
        # for some cells at exactly 125 C (G92b). A hint only; the output check still applies.
        ics += ".nodeset " + " ".join(f"v(n_{q})={v * vdd}" for q, v in p["expect"].items()) + "\n"
    d = (f"* {cell}\n{K['models']}\n.include {K['cells']}\nVDD VDD 0 {vdd}\n" + "\n".join(src) + "\n" + ics
         + f"X1 {' '.join(nodes)} {cell}\n.control\n" + "\n".join(meas) + "\n.endc\n.end\n")
    return d


def is_capture(info, p):
    """A state whose stored value is set by a capture sequence (not forced, not combinational)."""
    return SETTLE and info["seq"] is not None and not p["forced"]


CONT = (10e-3, 100e-6)                    # G92c continuation transient: end and maximum step, s
# G92d: the continuation runs in stages ending at these times after the capture (s), each stage continuing from the last one's
# end with a maximum step of 1/100 of its length. The state is settled at the first stage end whose supply current is within
# FLAT of the current one decade earlier; its value is that current. Not flat by the last stage: the plan fails.
STAGES = (1e-4, 1e-3, 1e-2, 1e-1, 1.0)
FLAT = 0.005
# ...or within FLOOR_A of it (A). The ASAP7 supply current at 25 C moves in steps of about 0.9 pA from stage to stage, whatever
# abstol, vntol or reltol (G92d dry run): a resolution floor, about 0.4% of a 150-250 pW flip-flop. Two steps of it are noise.
FLOOR_A = 2e-12
CONT_OPTS = ""                            # extra .options for continuation decks only
RETRY = True                             # G92d: a failed constant-input solve is retried once without its .nodeset hint


def settle_deck(cell, info, order, p, kit, t, last, mode, span=None):
    """Settling, at temperature t with every input constant at its final level.
    mode 'cont': continue the transient from `last` (.ic, uic) for `span` = (length, maximum step) s, default CONT; with no
                 edges left the step may grow to the maximum.
    mode 'op':   DC solve with every node seeded (.nodeset) from `last`. G92c used its solution as the state's value; G92d keeps
                 it only as a cross-check, because seeded DC can land on the other stored value of a bistable cell (G92c)."""
    span = span or CONT
    K = KITS[kit]
    vdd = K["vdd"]
    src = [f"V{q} n_{q} 0 {lv * vdd}" for q, lv in p["F"].items()]
    driven = {f"n_{q}".lower() for q in p["F"]} | {"vdd", "0"}
    seeds = []
    for n, x in last.items():
        m = re.fullmatch(r"v\((.+)\)", n)
        n = (m.group(1) if m else n).lower()
        if n == "time" or "#" in n or n.startswith("i(") or n in driven:
            continue
        seeds.append(f"v({n})={x:.9g}")
    nodes = ["VDD" if q == "VDD" else "0" if q in ("VSS", "GND") else f"n_{q}" for q in order]
    if mode == "cont":
        ctl = ["set filetype=binary", f"option temp={t}", f"tran 1n {span[0]:.6g} 0 {span[1]:.6g} uic", f"write c{t}.raw"]
        # Gear: the trapezoidal rule rings at large steps, and the last point's supply current then carries capacitor
        # current of either sign (dry run: IHP flops read 5,000-160,000 pW against about 600 pW settled)
        init = f".options method=gear {CONT_OPTS}\n" + "".join(f".ic {s}\n" for s in seeds)
    else:
        ctl = [f"option temp={t}", "op", f"let il{t} = i(vdd)", f"print il{t}"]
        for q in p["expect"]:
            ctl += [f"let v_{q}_{t} = v(n_{q})", f"print v_{q}_{t}"]
        init = "".join(f".nodeset {s}\n" for s in seeds)
    return (f"* {cell} settle {mode} {t}C\n{K['models']}\n.include {K['cells']}\nVDD VDD 0 {vdd}\n" + "\n".join(src) + "\n" + init
            + f"X1 {' '.join(nodes)} {cell}\n.control\n" + "\n".join(ctl) + "\n.endc\n.end\n")


def _current(last):
    for k in ("i(vdd)", "vdd#branch"):
        if k in last:
            return last[k]
    return None


def _parse(out, p, vdd, passive=False):
    il = {int(t): float(x) for t, x in re.findall(r"^il(\d+)\s*=\s*([-+0-9.eE]+)", out, re.M)}
    pw = {t: abs(i) * vdd * 1e12 for t, i in il.items()}
    if passive:
        for q, lv in p["F"].items():
            for t, x in re.findall(rf"^ii_{q}_(\d+)\s*=\s*([-+0-9.eE]+)", out, re.M | re.I):
                pw[int(t)] = pw.get(int(t), 0.0) + abs(float(x)) * lv * vdd * 1e12
    v = {}
    for q, t, x in re.findall(r"^v_(\w+?)_(\d+)\s*=\s*([-+0-9.eE]+)", out, re.M):
        v.setdefault(q.upper(), {})[int(t)] = float(x)
    want = {q.upper(): lv for q, lv in dict(p["expect"], **p["ic"]).items()}
    ok = len(il) == len(TEMPS) and all(len(v.get(q, {})) == len(TEMPS) and all(abs(x - lv * vdd) < 0.1 * vdd for x in v[q].values()) for q, lv in want.items())
    # G92c: an aborted analysis prints zeros for its measurements, which passed G92b's level check when the planned level
    # was 0 (46 ASAP7 states). Any abort or failed measurement now fails the plan.
    ok = ok and not ABORT.search(out)
    return pw, v, want, ok


# G92d adds a transient that ends at its first point ("No. of Data Rows : 1"): LVT AOI311xp33 at 125 C in G92c printed no
# abort text, only a one-row transient whose measurements read 0
ABORT = re.compile(r"simulation\(s\) aborted|timestep too small|failed!|no convergence|singular matrix|No\. of Data Rows\s*:\s*[01]\s*$",
                   re.I | re.M)


def solve(job):
    cell, key, d, p, kit, passive = job[:6]
    ctx = job[6] if len(job) > 6 else None
    vdd = KITS[kit]["vdd"]
    name = f"{cell}_{abs(hash(key))}"
    if ctx is not None and is_capture(ctx["info"], p):
        out, files = ngspice(name, d, KITS[kit]["osdi"], keep=[f"r{t}.raw" for t in TEMPS])
        tpw, tv, want, tok = _parse(out, p, vdd)
        pw, v, trace, flat, t_settled, souts, dcpw, dcv = {}, {}, {}, {}, {}, [], {}, {}
        lvl = lambda x, q: x is not None and abs(x - want[q] * vdd) < 0.1 * vdd
        for t in TEMPS:
            if f"r{t}.raw" not in files:
                continue
            last, ok_t, prev, elapsed, trace[t] = raw_last(files[f"r{t}.raw"]), True, None, 0.0, []
            for end in STAGES:
                span = end - elapsed
                co, cf = ngspice(f"{name}_c{t}_{end:g}", settle_deck(cell, ctx["info"], ctx["order"], p, kit, t, last, "cont", (span, span / 100)),
                                 KITS[kit]["osdi"], keep=[f"c{t}.raw"])
                if f"c{t}.raw" not in cf or ABORT.search(co):
                    souts.append(co)
                    ok_t = False
                    break
                last, elapsed = raw_last(cf[f"c{t}.raw"]), end
                i = _current(last)
                cur = abs(i) * vdd * 1e12 if i is not None else None
                lv = {q.upper(): last.get(f"n_{q}".lower(), last.get(f"v(n_{q})".lower())) for q in p["expect"]}
                trace[t].append((end, cur))
                if cur is None or not all(lvl(x, q) for q, x in lv.items()):
                    ok_t = False                              # the stored value was lost during the continuation
                    break
                if prev and abs(cur - prev) <= max(FLAT * prev, FLOOR_A * vdd * 1e12):
                    pw[t], v[t], flat[t], t_settled[t] = cur, lv, cur / prev - 1, end
                    break
                prev = cur
            if not ok_t or t not in pw:
                continue
            # cross-check only (not part of ok): DC seeded from the settled point; G92c showed it can flip a bistable cell
            so = ngspice(f"{name}_s{t}", settle_deck(cell, ctx["info"], ctx["order"], p, kit, t, last, "op"), KITS[kit]["osdi"])
            dp, dv, _, _ = _parse(so, p, vdd)
            if t in dp:
                dcpw[t] = dp[t]
                dcv[t] = all(lvl(dv.get(q, {}).get(t), q) for q in want)
        sok = len(pw) == len(TEMPS)
        ok = tok and sok
        vv = {q.upper(): {t: v[t][q.upper()] for t in v} for q in p["expect"]} if v else None
        return cell, key, dict(spice_pW=pw, tran_pW=tpw, v=vv, tran_v=tv or None, expect=want, s=p["s"], ok=ok, tran_ok=tok, settle_ok=sok,
                               settle_flat=flat, settle_t=t_settled, settle_trace=trace,
                               dc_pW=dcpw, dc_agree={t: dcpw[t] / pw[t] - 1 for t in dcpw if pw.get(t)}, dc_levels_ok=dcv,
                               **({} if ok else {"tail": (out[-600:] if not tok else souts[-1][-600:] if souts else "not flat by the last stage")}))
    out = ngspice(name, d, KITS[kit]["osdi"])
    pw, v, want, ok = _parse(out, p, vdd, passive)
    retried = False
    if not ok and RETRY and re.search(r"^\.nodeset", d, re.M):
        # G92d: one retry without the output-level hint. In G92c LVT AOI311xp33 (all inputs low) stopped at its first point at
        # 125 C with the hint and solves without it (dry run). The output check still applies.
        out = ngspice(name + "_r", re.sub(r"^\.nodeset[^\n]*\n", "", d, flags=re.M), KITS[kit]["osdi"])
        pw, v, want, ok = _parse(out, p, vdd, passive)
        retried = True
    return cell, key, dict(spice_pW=pw, v=v or None, expect=want, s=p["s"], ok=ok, **({"retried": True} if retried else {}),
                           **({} if ok else {"tail": out[-600:]}))


def write_lib(txt, cells, T):
    """Shipped text with every non-VSS leakage value replaced by the SPICE value at T."""
    pieces, last = [], 0
    for name, s, e in blocks(txt, r"\bcell"):
        c = cells.get(name)
        body = txt[s:e]
        if c and c.get("solved"):
            sts = iter(c["states"])
            nb, l2 = [], 0
            for a, b, w, v, pg in leak_groups(body):
                g = body[a:b]
                if pg != "VSS":
                    g = re.sub(r"(value\s*:\s*)[-+0-9.eE]+", lambda m: f"{m.group(1)}{next(sts)['spice_pW'][T]:.6g}", g, count=1)
                nb += [body[l2:a], g]
                l2 = b
            body = "".join(nb + [body[l2:]])
            if c["cell_leak_pW"] is not None:
                body = re.sub(r"(cell_leakage_power\s*:\s*)[-+0-9.eE]+", lambda v: f"{v.group(1)}{c['cell_leak_new'][T]:.6g}", body, count=1)
        pieces += [txt[last:s], body]
        last = e
    return "".join(pieces + [txt[last:]])


def read(path):
    return (gzip.open(path, "rt") if path.endswith(".gz") else open(path)).read()


def build(kit, libs):
    """Parse every lib and plan every state. Returns (texts, cells, jobs)."""
    order = subckt_pins(KITS[kit]["cells"])
    texts, cells, jobs = {}, {}, []
    for lib in libs:
        txt = read(lib)
        texts[lib] = txt
        for name, c in parse_lib(txt).items():
            c["lib"] = os.path.basename(lib)
            cells[name] = c
            if name not in order:
                c["skip"] = "no SPICE subcircuit"
                continue
            if not c["states"]:
                c["states"] = [dict(when=None, lib_pW=c["cell_leak_pW"] or 0.0, cell_only=True)]
            for k, st in enumerate(c["states"]):
                w = st["when"] or ""
                mts = [w] if is_product(w) or not w else minterms(w)
                if len(mts) > 1:
                    st["minterms"] = mts
                st["parts"] = []
                for j, m in enumerate(mts):
                    ps, fl = plan(name, c, m)
                    for i, p in enumerate(ps):
                        passive = not c["funcs"] and not p["ic"]
                        jobs.append((name, (k, j, i), deck(name, c, order[name], p, kit), p, kit, passive, dict(info=c, order=order[name])))
                        st["parts"].append(dict(minterm=j, sub=i, **fl))
    return texts, cells, jobs


def main(kit, out_dir, jobs, libs):
    os.makedirs(out_dir, exist_ok=True)
    texts, cells, work = build(kit, libs)
    res = {}
    with ThreadPoolExecutor(jobs) as ex:
        for name, key, r in ex.map(solve, work):
            res[(name, key)] = r
    for name, c in cells.items():
        if "skip" in c:
            continue
        for k, st in enumerate(c["states"]):
            parts = [(pt, res[(name, (k, pt["minterm"], pt["sub"]))]) for pt in st["parts"]]
            for pt, r in parts:
                pt.update(r)
            reach = [(pt, r) for pt, r in parts if not pt.get("unreachable")]
            use = reach or parts                         # unreachable minterms leave the mean unless all are unreachable
            ok = all(r["ok"] for _, r in parts)
            st.update(ok=ok, unreachable=not reach, free=any(pt.get("free") for pt, _ in parts),
                      spice_pW={T: sum(r["spice_pW"][T] for _, r in use) / len(use) for T in TEMPS} if ok else {})
        c["solved"] = all(s.get("ok") for s in c["states"])
        if c["solved"] and c["cell_leak_pW"] is not None:
            old = [s["lib_pW"] for s in c["states"]]
            c["cell_leak_new"] = {T: (c["cell_leak_pW"] * sum(s["spice_pW"][T] for s in c["states"]) / sum(old)) if sum(old) > 0
                                  else sum(s["spice_pW"][T] for s in c["states"]) / len(old) for T in TEMPS}
    for lib, txt in texts.items():
        stem = re.sub(r"\.lib(\.gz)?$", "", os.path.basename(lib))
        mine = {n: c for n, c in cells.items() if c["lib"] == os.path.basename(lib)}
        for T in TEMPS:
            open(os.path.join(out_dir, f"{stem}_{T}C.lib"), "w").write(write_lib(txt, mine, T))
    json.dump(dict(kit=kit, libs=libs, temps=TEMPS, vdd=KITS[kit]["vdd"], cells=cells), open(os.path.join(out_dir, "leak_states.json"), "w"), indent=1, default=str)
    live = [(nm, s) for nm, c in cells.items() if "skip" not in c for s in c["states"]]
    bad = [(nm, s["when"]) for nm, s in live if not s.get("ok")]
    print(f"{kit}: {len(cells)} cells, {len(live)} states, {len(work)} solves, {sum(s['unreachable'] for _, s in live)} unreachable, "
          f"{sum(s['free'] for _, s in live)} free, {len(bad)} not ok, skipped: {[nm for nm, c in cells.items() if 'skip' in c]}")
    if bad:
        print("not ok:", bad[:30])
    return cells


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4:])
