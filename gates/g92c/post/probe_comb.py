"""G92c post-run check (not scored): why did combinational ASAP7 states move against G92b?
For chosen cells, solve each non-captured state's deck as written (8 ns transient), with the 1 fF shunt (G92b) and the
10 fF shunt (G92c), and also as a DC operating point (`op`) with each shunt. Prints pW per variant at each temperature.
Usage: probe_comb.py <kit> <cells,comma>"""
import sys, glob, re, os
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, "gates/g92c")
import leaklib_g92c as L          # G92c's generator, frozen; opentsense/power/leaklib.py has moved on to G92d
kit, want = sys.argv[1], sys.argv[2].split(",")
libs = sorted(glob.glob(f"gates/g92b/runs/main/{kit}/lib/ship/*"))
_, cells, jobs = L.build(kit, libs)
pick = [j for j in jobs if j[0] in want and not L.is_capture(j[6]["info"], j[3])
        and os.environ.get("W", "") in str(cells[j[0]]["states"][j[1][0]]["when"])]
vdd = L.KITS[kit]["vdd"]


def to_op(d):
    d = re.sub(r"tran 20p \S+", "op", d)
    d = re.sub(r"meas tran (il\d+) avg i\(vdd\) from=\S+ to=\S+", r"let \1 = i(vdd)\nprint \1", d)
    return re.sub(r"meas tran \S+ avg [^\n]+\n", "", d)


def run(job):
    cell, key, d = job[:3]
    res = {}
    for sh in ("1e-15", "1e-14"):
        for mode, dk in (("tran", d), ("op", to_op(d))):
            dk = re.sub(r"cshunt=1e-1[45]", f"cshunt={sh} {os.environ.get('OPTS', '')}", dk)
            out = L.ngspice(f"{cell}_{abs(hash(key))}_{mode}{sh}", dk, L.KITS[kit]["osdi"])
            v = {int(t): abs(float(x)) * vdd * 1e12 for t, x in re.findall(r"^il(\d+)\s*=\s*([-+0-9.eE]+)", out, re.M)}
            res[f"{mode}{sh}"] = {t: round(x, 2) for t, x in sorted(v.items())}
    return cell, cells[cell]["states"][key[0]]["when"], res


with ThreadPoolExecutor(int(os.environ.get("J", "2"))) as ex:
    for cell, when, res in ex.map(run, pick[: int(os.environ.get("N", "6"))]):
        print(cell, when, res, flush=True)
