"""G74 post-hoc (NOT gated, written after the verdict): bar (b) was weak because every registered case has amplification <= 1.05.
This repeats it on the converged G31b map runs, where amplification is large, and reports how near rho = 1 the boundary sits.
Usage: posthoc.py <inputs.npz> <exploratory code> <run dir>"""
import json
import os
import sys

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "run.py")).read().split("# ---------- plumbing check")[0]
exec(src)                                      # solvers, leakage models and loops, exactly as gated

res = json.load(open(os.path.join(RUN, "result.json")))
out = {}
for key, e in res["map"].items():
    if e["status"] != "ok":
        continue
    p = key.split("_"); k, d, h, s = int(p[0][1:]), float(p[1][1:]), float(p[2][1:]), float(p[3][1:])
    th = Periodic(h); r = loop_g31b(k, d, h, s, th, tol=1e-6)
    T1, Ts, _ = fixed_point(lambda T: th.nl(r["dyn"] + r["lk"](T), 1e-8), r["Tu"], np.max, tol=1e-7, iters=3000)
    meas = float((Ts.max() - r["Tu"].max()) / (T1.max() - r["Tu"].max()))
    rf = rho_tangent(th, r["lk"], Ts, r["dyn"] + r["lk"](Ts))
    out[key] = dict(rho_fixed=rf, rho_u=e["rho_u_tangent"], pred=1 / (1 - rf), meas=meas, err=abs(1 / (1 - rf) / meas - 1), dpeak=float(Ts.max() - r["Tu"].max()))
    print(key, {a: round(b, 4) for a, b in out[key].items()}, flush=True)
strong = {k: v for k, v in out.items() if v["meas"] >= 1.2}
rho_run = [e["rho_u_tangent"] for e in res["map"].values() if e["status"] != "ok"]
rho_conv = [e["rho_u_tangent"] for e in res["map"].values() if e["status"] == "ok"]
sm = dict(converged_runs=len(out), max_rho_fixed=max(v["rho_fixed"] for v in out.values()), max_meas=max(v["meas"] for v in out.values()), strong_runs=len(strong),
          strong_worst_err=max([v["err"] for v in strong.values()], default=None), strong_within_25pct=sum(v["err"] <= 0.25 for v in strong.values()),
          min_rho_u_runaway=min(rho_run), max_rho_u_converged=max(rho_conv), rho_gt1_at_u_but_fixed_lt1=[k for k, v in out.items() if v["rho_u"] >= 1])
json.dump(dict(summary=sm, runs=out), open(os.path.join(RUN, "posthoc.json"), "w"), indent=1)
print(json.dumps(sm, indent=1))
