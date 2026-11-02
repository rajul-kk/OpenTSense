"""G74: spectral margin rho(R*D) of the leakage-temperature loop against measured runaway and amplification.
Usage: run.py <inputs.npz> <exploratory code> <run dir> [--plumbing]
--plumbing re-runs the loops only and compares them with the record; it computes no rho."""
import hashlib
import json
import os
import sys

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as sla

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from opentsense import manifest  # noqa: E402

INP, CODE, RUN = sys.argv[1:4]
PLUMBING = "--plumbing" in sys.argv
os.makedirs(RUN, exist_ok=True)
Z = np.load(INP)
G = 32
W = 510.555e-6
AREA = 510.555 ** 2 * 1e-6                     # mm^2
H = W / G
TIGHT = 1e-10

# ---------- thermal: G31 periodic unit cell, k(T) in silicon -------------------------------------
LAY = [(2e-6, "si"), (24e-6, "si"), (24e-6, "si"), (25e-6, 4.0), (250e-6, 400.0), (250e-6, 400.0)]
nz = len(LAY); n = nz * G * G
idx = np.arange(n).reshape(nz, G, G)
dz = np.array([l[0] for l in LAY]); zc = np.repeat(np.arange(nz), G * G)
is_si = np.array([l[1] == "si" for l in LAY])
la, lb, lz = [], [], []
for z in range(nz):
    for a, b in ((idx[z], np.roll(idx[z], -1, 0)), (idx[z], np.roll(idx[z], -1, 1))):
        la.append(a.ravel()); lb.append(b.ravel()); lz.append(np.full(G * G, z))
la, lb, lz = map(np.concatenate, (la, lb, lz))
va, vb, vz = idx[:-1].reshape(-1), idx[1:].reshape(-1), np.repeat(np.arange(nz - 1), G * G)
top = idx[-1].ravel()


def kc(T, nl):
    k = np.array([130.0 if l[1] == "si" else l[1] for l in LAY])[zc]
    if nl:
        k = np.where(is_si[zc], 130.0 * ((298.15 + T) / 300.0) ** -1.3, k)
    return k


def amat(k, htc):
    gl = 2 * k[la] * k[lb] / (k[la] + k[lb]) * dz[lz]
    gv = H * H / (dz[vz] / (2 * k[va]) + dz[vz + 1] / (2 * k[vb]))
    g = np.r_[gl, gv]; a_, b_ = np.r_[la, va], np.r_[lb, vb]
    d = np.zeros(n); np.add.at(d, a_, g); np.add.at(d, b_, g)
    d[top] += H * H / (dz[-1] / (2 * k[top]) + 1 / htc)
    return sp.csc_matrix((np.r_[-g, -g, d], (np.r_[a_, b_, np.arange(n)], np.r_[b_, a_, np.arange(n)])), shape=(n, n))


class Periodic:
    def __init__(self, htc):
        self.htc = htc; self.lu = sla.splu(amat(kc(0, False), htc))

    def full(self, P, tol=1e-4):
        q = np.zeros(n); q[idx[0].ravel()] = P.ravel(); T = self.lu.solve(q)
        for _ in range(200):
            d = self.lu.solve(q - amat(kc(T, True), self.htc) @ T); T = T + d
            if not np.isfinite(d).all() or np.abs(d).max() < tol:
                break
        return T

    def nl(self, P, tol=1e-4):
        return self.full(P, tol)[idx[0].ravel()].reshape(G, G)

    def linear(self, P):
        q = np.zeros(n); q[idx[0].ravel()] = P.ravel()
        return self.lu.solve(q)[idx[0].ravel()].reshape(G, G)


# ---------- thermal: G37 die-sized solver, adiabatic sides, constant k ----------------------------
class DieSolver:
    def __init__(self, htc):
        L = [(2e-6, 130.0), (24e-6, 130.0), (24e-6, 130.0), (25e-6, 4.0), (250e-6, 400.0), (250e-6, 400.0)]
        m = len(L); N = m * G * G; ix = np.arange(N).reshape(m, G, G)
        dzz = np.array([l[0] for l in L]); k = np.array([l[1] for l in L])
        r, c, v = [], [], []; dg = np.zeros(N)

        def add(a, b, gg):
            r.extend([a, b]); c.extend([b, a]); v.extend([-gg, -gg]); np.add.at(dg, a, gg); np.add.at(dg, b, gg)
        for z in range(m):
            add(ix[z, :-1, :].ravel(), ix[z, 1:, :].ravel(), np.full((G - 1) * G, k[z] * dzz[z]))
            add(ix[z, :, :-1].ravel(), ix[z, :, 1:].ravel(), np.full((G - 1) * G, k[z] * dzz[z]))
        for z in range(m - 1):
            add(ix[z].ravel(), ix[z + 1].ravel(), np.full(G * G, H * H / (dzz[z] / (2 * k[z]) + dzz[z + 1] / (2 * k[z + 1]))))
        dg[ix[-1].ravel()] += H * H / (dzz[-1] / (2 * k[-1]) + 1 / htc)
        self.lu = sla.splu(sp.csc_matrix((np.r_[np.concatenate(v), dg], (np.r_[np.concatenate(r), np.arange(N)], np.r_[np.concatenate(c), np.arange(N)])), shape=(N, N)))
        self.N, self.act = N, ix[0].ravel()

    def linear(self, P):
        q = np.zeros(self.N); q[self.act] = P.ravel()
        return self.lu.solve(q)[self.act].reshape(G, G)


# ---------- sky130 leakage models -----------------------------------------------------------------
TS = Z["sky_T"]; TYPES = [str(t) for t in Z["sky_types"]]; LNF = {t: Z[f"sky_lnF_{t}"] for t in TYPES}


def f_t(ln, T):
    T = np.asarray(T, float); y = np.interp(T, TS, ln)
    y = np.where(T > TS[-1], ln[-1] + (T - TS[-1]) * (ln[-1] - ln[-2]) / (TS[-1] - TS[-2]), y)
    return np.exp(np.where(T < TS[0], ln[0], y))


def curve_leak(L, Tabs):                       # G31b: per type group, the rest on the leakage-weighted mean curve
    wmix = sum(L[k].sum() * np.exp(LNF[t]) for k, t in enumerate(TYPES)) / L[:-1].sum()
    return sum(L[k] * f_t(LNF[t], Tabs) for k, t in enumerate(TYPES)) + L[-1] * f_t(np.log(wmix), Tabs)


def expo_leak(L25, L100, rise):                # G31: exponential between the library corners
    r = np.where((L25 > 0) & (L100 > 0), L100 / np.where(L25 > 0, L25, 1), 1.0)
    return L25 * r ** (rise / 75.0)


# ---------- margin ----------------------------------------------------------------------------------
def spectral(matvec, size=G * G):
    op = sla.LinearOperator((size, size), matvec=matvec, dtype=float)
    v0 = np.ones(size)
    return float(np.abs(sla.eigs(op, k=1, which="LM", v0=v0, ncv=24, tol=1e-6, maxiter=2000, return_eigenvectors=False)[0]))


def diag_d(lk, T):
    return lk(T + 0.5) - lk(T - 0.5)


def rho_const(th, lk, T):
    D = diag_d(lk, T)
    return spectral(lambda v: th.linear(D * v.reshape(G, G)).ravel())


def rho_tangent(th, lk, T, P0):
    D = diag_d(lk, T); base = th.nl(P0, TIGHT); eps = 1e-5 * P0.sum() / max(np.abs(D).sum(), 1e-300)

    def mv(v):
        w = D * v.reshape(G, G); s = eps / max(np.abs(v).max(), 1e-300)
        return ((th.nl(P0 + s * w, TIGHT) - base) / s).ravel()
    return spectral(mv)


# ---------- loops -----------------------------------------------------------------------------------
def sky_scale(k, dens, share):
    dyn0, L0 = Z[f"sky_dyn_k{k}"], Z[f"sky_L_k{k}"]
    Pt = dens * AREA
    L85 = curve_leak(L0, np.full((G, G), 85.0)).sum()
    return dyn0 * (1 - share) * Pt / dyn0.sum(), L0 * share * Pt / L85


def loop_g31b(k, dens, htc, share, th, tol=0.01):
    dyn, L = sky_scale(k, dens, share); L25 = L.sum(0)
    lk = lambda T: curve_leak(L, 25 + T)       # noqa: E731
    Tu = th.linear(dyn + L25); T = Tu.copy()
    with np.errstate(over="ignore", invalid="ignore"):
        for it in range(1, 61):
            Tn = th.nl(dyn + lk(T), min(tol, 1e-4))
            if not np.isfinite(Tn).all() or Tn.max() > 175:     # as recorded: 175 K of rise, i.e. 200 C
                return dict(status="runaway", iters=it, dyn=dyn, L25=L25, lk=lk, Tu=Tu)
            if np.abs(Tn - T).max() < tol:
                return dict(status="ok", iters=it, peak_C=float(25 + Tn.max()), T=Tn, dyn=dyn, L25=L25, lk=lk, Tu=Tu)
            T = Tn
    return dict(status="no_convergence", dyn=dyn, L25=L25, lk=lk, Tu=Tu)


def loop_g31(k, th):
    dyn0, L0, L100 = Z[f"sky_dyn_k{k}"], Z[f"sky_L_k{k}"].sum(0), Z[f"sky_L100_k{k}"]
    Pt = 1.0 * AREA
    L85 = expo_leak(L0, L100, np.full((G, G), 60.0)).sum()
    dyn, L25, Lh = dyn0 * 0.7 * Pt / dyn0.sum(), L0 * 0.3 * Pt / L85, L100 * 0.3 * Pt / L85
    lk = lambda T: expo_leak(L25, Lh, T)       # noqa: E731
    Tu = th.linear(dyn + L25); T = Tu.copy(); status = "no_convergence"
    with np.errstate(over="ignore", invalid="ignore"):
        for it in range(1, 41):
            Tn = th.nl(dyn + lk(T))
            if np.isfinite(Tn).all() and np.abs(Tn - T).max() < 0.01:
                status = "ok"; break
            T = Tn
    return dict(status=status, dyn=dyn, L25=L25, lk=lk, Tu=Tu)


def fixed_point(step, Tu, peak, tol=TIGHT, iters=500):
    T1 = step(Tu); T = T1
    for it in range(iters):
        Tn = step(T)
        if np.abs(Tn - T).max() < tol:
            return T1, Tn, it + 1
        T = Tn
    raise RuntimeError("no fixed point")


def g37_case(k, htc):
    th = DieSolver(htc); dyn, L = Z[f"sky_dyn_k{k}"], Z[f"sky_L_k{k}"]; L25 = L.sum(0)
    lk = lambda T: curve_leak(L, 25 + T)       # noqa: E731
    Tu = th.linear(dyn + L25)
    T1, Ts, it = fixed_point(lambda T: th.linear(dyn + lk(T)), Tu, np.max)
    return dict(th=th, lk=lk, dyn=dyn, Tu=Tu, T1=T1, Ts=Ts, iters=it)


A7A = Z["a7_A"]; n2 = 3600; TT = Z["a7_T"]


def a7_curve(c, T):
    ln = np.log(c); T = np.asarray(T, float); y = np.interp(T, TT, ln)
    return np.exp(np.where(T > TT[-1], ln[-1] + (T - TT[-1]) * (ln[-1] - ln[-2]) / (TT[-1] - TT[-2]), y))


def a7_bins(Tf):
    t = Tf[:n2].reshape(60, 60)[20:40, 20:40].reshape(10, 2, 10, 2).mean((1, 3)).ravel()
    c = Tf[n2:].reshape(60, 60)[20:40, 20:40].reshape(10, 2, 10, 2).mean((1, 3)).ravel()
    return np.r_[t, Tf[:n2].mean(), c, Tf[n2:].mean()]


def a7_case(s):
    pt, pc = Z[f"a7_pt_{s}"], Z[f"a7_pc_{s}"]
    L25 = np.r_[pt * 0.004, pc * 0.00035]; dyn = np.r_[pt, pc] - L25
    lk = lambda Tb: np.r_[L25[:101] * a7_curve(Z["a7_curve_tpu"], 25 + Tb[:101]), L25[101:] * a7_curve(Z["a7_curve_R"], 25 + Tb[101:])]  # noqa: E731
    Tu = A7A @ np.r_[pt, pc]
    T1, Ts, it = fixed_point(lambda T: A7A @ (dyn + lk(a7_bins(T))), Tu, np.max)
    return dict(lk=lk, dyn=dyn, Tu=Tu, T1=T1, Ts=Ts, iters=it, pt=pt)


A7M = np.stack([a7_bins(A7A[:, j]) for j in range(202)], 1)


def a7_rho(c, Tf):
    b = a7_bins(Tf)
    D = np.array([(c["lk"](b + 0.5 * e) - c["lk"](b - 0.5 * e))[i] for i, e in enumerate(np.eye(202))])
    return float(np.abs(np.linalg.eigvals(A7M * D)).max())


# ---------- plumbing check ----------------------------------------------------------------------------
PER = {h: Periodic(h) for h in (1e4, 2e4, 5e4, 1e5)}
rec = json.load(open(os.path.join(CODE, "sens/g35/g31b.json")))["results"]
g37 = json.load(open(os.path.join(CODE, "sens/g37/g37_res.json")))["summary"]
g41 = json.load(open(os.path.join(CODE, "sens/g41/g41_res.json")))["stack"]
MAP = [(k, d, h, s) for k in range(4) for d in (0.5, 1.0) for h in (1e4, 2e4, 5e4, 1e5) for s in (0.1, 0.3, 0.5)]
loops = {}
worst, bad = 0.0, []
for k, d, h, s in MAP:
    key = f"k{k}_d{d}_h{h:.0e}_s{s}"; r = loops[key] = loop_g31b(k, d, h, s, PER[h]); e = rec[key]
    if r["status"] != e["status"]:
        bad.append((key, e["status"], r["status"]))
    elif r["status"] == "ok":
        worst = max(worst, abs(r["peak_C"] - e["peak_C"]))
g37c = {f"k{k}_h{h:.0e}": g37_case(k, h) for h in (2e3, 1e4) for k in range(4)}
g37_err = {key: abs(25 + c["Ts"].max() - g37[key]["py_peak_C"]) for key, c in g37c.items()}
a7c = {s: a7_case(s) for s in range(4)}
a7_err = {s: max(abs(25 + c["Ts"][:n2].max() - g41[str(s)]["tpu_peak_C"]), abs(25 + c["Ts"][n2:].max() - g41[str(s)]["cpu_peak_C"])) for s, c in a7c.items()}
plumb = dict(g31b_status_mismatches=bad, g31b_worst_peak_K=worst, g37_worst_peak_K=max(g37_err.values()), g41_worst_peak_K=max(a7_err.values()))
plumb["ok"] = bool(not bad and worst <= 0.5 and plumb["g37_worst_peak_K"] <= 0.05 and plumb["g41_worst_peak_K"] <= 0.05)
print("plumbing", json.dumps(plumb), flush=True)
if PLUMBING or not plumb["ok"]:
    json.dump(plumb, open(os.path.join(RUN, "plumbing.json"), "w"), indent=1)
    sys.exit(0 if PLUMBING else 1)

# ---------- gate ----------------------------------------------------------------------------------------
cases = {}
for k in range(4):                             # runaway set
    r = loop_g31(k, PER[1e4]); th = PER[1e4]
    cases[f"G31_k{k}"] = dict(group="runaway", measured=r["status"], rho_tangent=rho_tangent(th, r["lk"], r["Tu"], r["dyn"] + r["L25"]), rho_const=rho_const(th, r["lk"], r["Tu"]), peak_u_C=float(25 + r["Tu"].max()))
    r = loop_g31b(k, 1.0, 1e4, 0.3, th)
    cases[f"G31b_k{k}"] = dict(group="runaway", measured=r["status"], rho_tangent=rho_tangent(th, r["lk"], r["Tu"], r["dyn"] + r["L25"]), rho_const=rho_const(th, r["lk"], r["Tu"]), peak_u_C=float(25 + r["Tu"].max()))
    print(f"k{k}", cases[f"G31_k{k}"], cases[f"G31b_k{k}"], flush=True)


def amp(Tu, T1, Ts):
    return float((Ts.max() - Tu.max()) / (T1.max() - Tu.max()))


for key, c in g37c.items():
    rho_u, rho_f = rho_const(c["th"], c["lk"], c["Tu"]), rho_const(c["th"], c["lk"], c["Ts"])
    m = amp(c["Tu"], c["T1"], c["Ts"]); p = 1 / (1 - rho_f)
    cases[f"G37_{key}"] = dict(group="converged", measured="ok", rho_const=rho_u, rho_fixed=rho_f, amp_pred=p, amp_meas=m, amp_err=abs(p / m - 1), peak_C=float(25 + c["Ts"].max()), rise_K=float(c["Ts"].max() - c["Tu"].max()))
    print(key, cases[f"G37_{key}"], flush=True)
for s, c in a7c.items():
    rho_u, rho_f = a7_rho(c, c["Tu"]), a7_rho(c, c["Ts"])
    m = amp(c["Tu"], c["T1"], c["Ts"]); p = 1 / (1 - rho_f)
    cases[f"G41_s{s}"] = dict(group="converged", measured="ok", rho_const=rho_u, rho_fixed=rho_f, amp_pred=p, amp_meas=m, amp_err=abs(p / m - 1), peak_C=float(25 + c["Ts"].max()), rise_K=float(c["Ts"].max() - c["Tu"].max()))
    print("G41", s, cases[f"G41_s{s}"], flush=True)


def a_ok(c):
    rs = [c["rho_const"]] + ([c["rho_tangent"]] if "rho_tangent" in c else [])
    return all(r >= 1 for r in rs) if c["measured"] != "ok" else all(r < 1 for r in rs)


run_set = [k for k, c in cases.items() if c["group"] == "runaway"]
bar_status = {k: cases[k]["measured"] != "ok" for k in run_set}
bar_a = {k: a_ok(c) for k, c in cases.items()}
bar_b = {k: c["amp_err"] <= 0.25 for k, c in cases.items() if "amp_err" in c}

# reported, not gated: the same test on the whole G31b map
mapr = {}
for k, d, h, s in MAP:
    key = f"k{k}_d{d}_h{h:.0e}_s{s}"; r = loops[key]; th = PER[h]
    e = dict(status=r["status"], rho_u_tangent=rho_tangent(th, r["lk"], r["Tu"], r["dyn"] + r["L25"]), rho_u_const=rho_const(th, r["lk"], r["Tu"]), peak_u_C=float(25 + r["Tu"].max()))
    if r["status"] == "ok":
        e["rho_fixed"] = rho_tangent(th, r["lk"], r["T"], r["dyn"] + r["lk"](r["T"]))
    mapr[key] = e
cm = {f"{'run' if e['status'] != 'ok' else 'conv'}_{'ge1' if e['rho_u_tangent'] >= 1 else 'lt1'}": 0 for e in mapr.values()}
for e in mapr.values():
    cm[f"{'run' if e['status'] != 'ok' else 'conv'}_{'ge1' if e['rho_u_tangent'] >= 1 else 'lt1'}"] += 1

ok_a, ok_b = all(bar_a.values()), all(bar_b.values())
res = dict(gate="G74", verdict="PASS" if ok_a and ok_b else "FAIL", bar_a=ok_a, bar_b=ok_b, bar_a_failures=[k for k, v in bar_a.items() if not v], bar_b_failures=[k for k, v in bar_b.items() if not v],
           runaway_confirmed=bar_status, cases=cases, plumbing=plumb, map_confusion_rho_u=cm, map=mapr, inputs_sha256=hashlib.sha256(open(INP, "rb").read()).hexdigest())
json.dump(res, open(os.path.join(RUN, "result.json"), "w"), indent=1, default=float)
manifest.write(os.path.join(RUN, "manifest.json"))
print(json.dumps({k: res[k] for k in ("verdict", "bar_a", "bar_b", "bar_a_failures", "bar_b_failures", "map_confusion_rho_u")}, indent=1))
