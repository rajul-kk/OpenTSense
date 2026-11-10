import glob, sys, os, subprocess, tempfile, re, time
from opentsense.power import leaklib as L
texts, cells, jobs = L.build("asap7", sorted(glob.glob("gates/g92b/dry/lib/asap7*")))
j = [j for j in jobs if j[0] == "SDFHx1_ASAP7_75t_R" and j[1][0] == 2][0]
base = j[2][:j[2].find("option temp=50")] + ".endc\n.end\n"
def run(d):
    with tempfile.TemporaryDirectory() as t:
        open(os.path.join(t, ".spiceinit"), "w").write("set num_threads=1\n" + "osdi '/opt/spice/osdi/bsimcmg.osdi'\n")
        open(os.path.join(t, "x.cir"), "w").write(d)
        t0 = time.time(); r = subprocess.run(["ngspice", "-b", "x.cir"], cwd=t, capture_output=True, text=True)
        return r.stderr[-300:].replace(chr(10)," | "), round(time.time() - t0, 1), re.findall(r"^(il25|v_qn_25)\s*=\s*(\S+)", r.stdout, re.M), "aborted" in r.stderr
for name, opt in [("cshunt1e-18", "option cshunt=1e-18"), ("cshunt1e-17", "option cshunt=1e-17"), ("gear", "option method=gear"),
                  ("gear+cshunt1e-18", "option method=gear\noption cshunt=1e-18")]:
    print(name, run(base.replace(".control\n", ".control\n" + opt + "\n")), flush=True)
slow = base.replace("2.05n 0.7", "2.2n 0.7").replace("5.05n", "5.2n")
print("slow edge 200ps", run(slow), flush=True)
