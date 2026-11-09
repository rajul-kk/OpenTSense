"""G81d evaluation (registration.md). Usage: python evaluate.py <run dir with mm.log, conv.log, mlp1.log>"""
import json
import os
import re
import sys

import numpy as np

RUN = sys.argv[1]
G51 = dict(mm=37227, conv=2197389, mlp1=4314792)
KS = dict(mm=100, conv=4, mlp1=3)


def parse(path):
    txt = open(path, errors="replace").read()
    stamps = {int(i): int(c) for i, c in re.findall(r"G81D_STAMP (\d+) (\d+)", txt)}
    done = re.search(r"G81D_DONE (\d+)", txt)
    rc = re.search(r"RUN_DONE rc=(\d+) wall=(\d+)s", txt)
    act = {"retire": {}, "gbusy": {}}
    for m in re.finditer(r"^ACT (retire|gbusy) (\d+) (\d+)$", txt, re.M):
        act[m.group(1)][int(m.group(2))] = int(m.group(3))
    return stamps, (int(done.group(1)) if done else None), (int(rc.group(1)), int(rc.group(2))) if rc else (None, None), act


def series(d, n):
    """window counts as an array of length n; missing windows are NaN"""
    a = np.full(n, np.nan)
    for w, v in d.items():
        if w < n:
            a[w] = v / 1000
    return a


def frac(a, c0, c1):
    """overlap-weighted mean of window fractions over cycles [c0, c1); NaN windows are skipped"""
    w0, w1 = c0 // 1000, (c1 - 1) // 1000
    tot = wsum = 0.0
    for w in range(w0, w1 + 1):
        ov = min(c1, (w + 1) * 1000) - max(c0, w * 1000)
        if ov > 0 and not np.isnan(a[w]):
            tot += ov * a[w]; wsum += ov
    return tot / wsum


out, tl = {}, {}
for name in ("mm", "conv", "mlp1"):
    stamps, done, (rc, wall), act = parse(os.path.join(RUN, f"{name}.log"))
    K = KS[name]
    r = dict(rc=rc, wall_s=wall, done=done, n_stamps=len(stamps))
    complete = rc == 0 and done == K and sorted(stamps) == list(range(K + 1))
    if not complete:
        r.update(a=False); out[name] = r; continue
    s = [stamps[i] for i in range(K + 1)]
    n_exp = s[K] // 1000                                     # windows fully elapsed by the final stamp
    ret, bus = series(act["retire"], n_exp + 1), series(act["gbusy"], n_exp + 1)   # + the partial window holding the last stamp
    parsed = min(np.isfinite(ret[:n_exp]).mean(), np.isfinite(bus[:n_exp]).mean())
    r.update(parsed_frac=float(parsed), a=bool(complete and parsed >= 0.99))
    dur = np.diff(s)
    r["iter_cycles"] = dur.tolist()
    r["v_iter1_vs_g51_rel"] = float(dur[0] / G51[name] - 1)
    r["v"] = bool(abs(r["v_iter1_vs_g51_rel"]) <= 0.01)
    gb = np.array([frac(bus, s[i], s[i + 1]) for i in range(K)]); rt = np.array([frac(ret, s[i], s[i + 1]) for i in range(K)])
    st = slice(1, K)
    md, mg, mr = np.median(dur[st]), np.median(gb[st]), np.median(rt[st])
    r.update(iter_busy=gb.tolist(), iter_retire=rt.tolist(),
             b_dur_max_rel=float(np.max(np.abs(dur[st] / md - 1))), b_busy_max_abs=float(np.max(np.abs(gb[st] - mg))),
             b_retire_max_abs=float(np.max(np.abs(rt[st] - mr))))
    r["b"] = bool(r["b_dur_max_rel"] <= 0.01 and r["b_busy_max_abs"] <= 0.01 and r["b_retire_max_abs"] <= 0.01)
    # reported: steady-state duty, correlation, cold start
    w0, w1 = s[1] // 1000 + 1, s[K] // 1000                # whole windows inside iterations 2..K
    rr, bb = ret[w0:w1], bus[w0:w1]; ok = np.isfinite(rr) & np.isfinite(bb)
    r.update(steady_busy=float(mg), steady_retire=float(mr), iter1_busy=float(gb[0]), iter1_retire=float(rt[0]),
             steady_corr=float(np.corrcoef(rr[ok], bb[ok])[0, 1]) if rr[ok].std() > 0 and bb[ok].std() > 0 else None,
             steady_windows=int(ok.sum()), prefix_cycles=int(s[0]))
    # one steady period (the last iteration) as the deliverable timeline
    p0, p1 = s[K - 1] // 1000, s[K] // 1000
    tl[f"{name}_retire"], tl[f"{name}_busy"] = ret[p0:p1], bus[p0:p1]
    out[name] = r
v = all(out[n].get("v", False) for n in out)
a = all(out[n].get("a", False) for n in out)
b = all(out[n].get("b", False) for n in out)
verdict = "INCONCLUSIVE" if not v and a else ("PASS" if v and a and b else "FAIL")
res = dict(workloads=out, v=v, a=a, b=b, verdict=verdict, g51_cycles=G51, K=KS)
json.dump(res, open(os.path.join(RUN, "result.json"), "w"), indent=1)
np.savez(os.path.join(RUN, "timelines.npz"), **tl)
for n, r in out.items():
    print(n, {k: (round(x, 4) if isinstance(x, float) else x) for k, x in r.items() if not k.startswith("iter_")})
print("G81d:", verdict, dict(v=v, a=a, b=b))
