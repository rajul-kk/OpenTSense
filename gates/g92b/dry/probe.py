import glob, time, collections
from concurrent.futures import ThreadPoolExecutor
from opentsense.power import leaklib as L
pick = {"ihp": ["sg13g2_antennanp", "sg13g2_sighold", "sg13g2_lgcp_1", "sg13g2_slgcp_1", "sg13g2_dllr_1", "sg13g2_sdfrbpq_1", "sg13g2_dfrbp_1", "sg13g2_inv_1"],
        "asap7": ["INVx1_ASAP7_75t_R", "NAND2x1_ASAP7_75t_R", "DFFHQNx1_ASAP7_75t_R", "DHLx1_ASAP7_75t_R", "DLLx1_ASAP7_75t_R", "ICGx1_ASAP7_75t_R", "DFFASRHQNx1_ASAP7_75t_R", "SDFHx1_ASAP7_75t_R", "SDFLx1_ASAP7_75t_R", "TIEHIx1_ASAP7_75t_R", "FAx1_ASAP7_75t_R"]}
for kit, pat in (("ihp", "sg13g2*.lib"), ("asap7", "asap7*")):
    texts, cells, jobs = L.build(kit, sorted(glob.glob(f"gates/g92b/dry/lib/{pat}")))
    js = [j for j in jobs if j[0] in pick[kit]]
    t = time.time()
    with ThreadPoolExecutor(12) as ex:
        rs = list(ex.map(L.solve, js))
    print(kit, len(js), "solves", round(time.time() - t), "s", flush=True)
    agg = collections.defaultdict(lambda: [0, 0, []])
    for (name, key, r), j in zip(rs, js):
        st = cells[name]["states"][key[0]]
        a = agg[name]; a[0] += 1; a[1] += r["ok"]
        if r["spice_pW"].get(25): a[2].append(st["lib_pW"] / r["spice_pW"][25])
        if not r["ok"]:
            print("  FAIL", name, st["when"], key, {q: round(v.get(25, -9), 3) for q, v in (r["v"] or {}).items()}, r["expect"], r["tail"][-200:].replace("\n", " | "))
    for n, (tot, ok, rr) in agg.items():
        print(f"  {n}: {ok}/{tot} ok, lib/spice25 {min(rr) if rr else 0:.2f}..{max(rr) if rr else 0:.2f}")
