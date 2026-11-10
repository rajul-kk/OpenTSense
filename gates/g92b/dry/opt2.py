import glob, os, subprocess, tempfile, re
from opentsense.power import leaklib as L
texts, cells, jobs = L.build("asap7", sorted(glob.glob("gates/g92b/dry/lib/asap7*")))
j = [j for j in jobs if j[0] == "SDFHx1_ASAP7_75t_R" and j[1][0] == 2][0]
base = j[2][:j[2].find("option temp=50")] + ".endc\n.end\n"
def run(d):
    with tempfile.TemporaryDirectory() as t:
        open(os.path.join(t, ".spiceinit"), "w").write("set num_threads=1\nosdi '/opt/spice/osdi/bsimcmg.osdi'\n")
        open(os.path.join(t, "x.cir"), "w").write(d)
        r = subprocess.run(["ngspice", "-b", "x.cir"], cwd=t, capture_output=True, text=True)
        return re.findall(r"^(il25|v_qn_25|i\(vdd\)|v\(n_qn\))\s*=\s*(\S+)", r.stdout, re.M), [l for l in r.stderr.splitlines() if "too small" in l][:1]
for opt in [".options cshunt=1e-17", ".options cshunt=1e-16 method=gear", ".options cshunt=1e-15"]:
    print(opt, run(base.replace("X1 ", opt + "\nX1 ")), flush=True)
# DC with nodeset at the final inputs
F = j[3]["F"]
src = "\n".join(f"V{q} n_{q} 0 {v*0.7}" for q, v in F.items())
for lv in (0, 1):
    d = f"* x\n.include /opt/spice/asap7/asap7_tt_osdi.lib\n.include /opt/spice/asap7/cells_R.sp\nVDD VDD 0 0.7\n{src}\n.nodeset v(n_QN)={lv*0.7}\nX1 n_CLK n_D n_QN n_SE n_SI VDD 0 SDFHx1_ASAP7_75t_R\n.control\noption temp=25\nop\nprint i(vdd) v(n_qn)\n.endc\n.end\n"
    print("op nodeset", lv, run(d))
