import glob, sys, os, subprocess, tempfile
from opentsense.power import leaklib as L
kit, cell, k = sys.argv[1], sys.argv[2], int(sys.argv[3])
texts, cells, jobs = L.build(kit, sorted(glob.glob("gates/g92b/dry/lib/" + ("sg13g2*.lib" if kit == "ihp" else "asap7*"))))
j = [j for j in jobs if j[0] == cell and j[1][0] == k][0]
d = j[2].replace("option temp=50", ".endc\n.end\n*")[:j[2].find("option temp=50")] + ".endc\n.end\n" if "one" in sys.argv else j[2]
with tempfile.TemporaryDirectory() as t:
    open(os.path.join(t, ".spiceinit"), "w").write("set num_threads=1\nsetcs sourcepath = ( $sourcepath /opt/spice/ihp/models /opt/spice/asap7 )\n" + "".join(f"osdi '/opt/spice/osdi/{m}.osdi'\n" for m in L.KITS[kit]["osdi"]))
    open(os.path.join(t, "x.cir"), "w").write(d)
    r = subprocess.run(["ngspice", "-b", "x.cir"], cwd=t, capture_output=True, text=True)
    print("STDERR", r.stderr[-2500:]); print("STDOUT tail", r.stdout[-800:])
