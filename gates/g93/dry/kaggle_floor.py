# OpenTSense G93 noise floor (18 Nov 2026), on a Kaggle CPU session: builds the three solvers as kaggle_probe_beol.py
# does (plus hotspot-lu-reuse.patch, as opentsense:g94b), runs tests/test_solvers.py, then floor.py per unit.
# The three parity units (S2 on the gated mesh, every solver) run first and the session stops if they miss
# floor_summary's parity rule against the image's units (floor_image/, A18). A unit that fails is logged and the next
# one runs; a unit starts only with its estimate left before LIMIT_S, capped at 3 x its estimate; the summary is
# rewritten after every unit, so a session killed late (HotSpot near the RAM limit) keeps it.
# Output: /kaggle/working/floor/<unit>.json, parity.json, floor_summary.json, floor_units.log.
import os, shutil, subprocess, sys, time
W = "/kaggle/working"; SRC = f"{W}/src"; T0 = time.time()
LIMIT_S = 11.5 * 3600                     # Kaggle stops a session at 12 h; leave time to save the output
EST = {1: {"ice": 300, "hs": 600, "pact": 300}, 2: {"ice": 2400, "hs": 9000, "pact": 2400}}   # s, generous
def sh(cmd, log=None, check=True):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, executable="/bin/bash")
    if log: open(f"{W}/{log}", "a").write(r.stdout + r.stderr)
    print(f"[{time.time() - T0:7.0f} s] rc {r.returncode}: {cmd[:120]}", flush=True)
    if check and r.returncode: print((r.stdout + r.stderr)[-3000:], flush=True); sys.exit(1)
    return r
inp = [os.path.join("/kaggle/input", d) for d in os.listdir("/kaggle/input")]
root = next(os.path.join(dp) for d in inp for dp, dn, fn in os.walk(d) if "opentsense" in dn and "gates" in dn)
shutil.copytree(root, SRC, dirs_exist_ok=True)
V = dict(l.strip().split("=", 1) for l in open(f"{SRC}/docker/versions.env") if "=" in l and not l.startswith("#"))
P = f"{SRC}/docker/patches"
sh("apt-get update -qq && apt-get install -y -qq --no-install-recommends bison flex libopenblas-dev libsuperlu-dev libblas-dev patch", "apt.log")
sh(f"git clone -q https://github.com/esl-epfl/3d-ice.git /opt/3d-ice && cd /opt/3d-ice && git checkout -q {V['ICE_COMMIT']} && patch -p1 < {P}/3d-ice-4953952.patch && "
   f"git clone -q https://github.com/xiaoyeli/superlu_mt.git superlu_mt-4.0.0 && git -C superlu_mt-4.0.0 checkout -q {V['SLU_COMMIT']} && "
   f"cp {P}/superlu_mt-4.0.0.make.inc superlu_mt-4.0.0/make.inc && mkdir -p superlu_mt-4.0.0/lib && "
   "sed -i 's/case 6: return (-50);/case 6: return (-400);/; s/case 7: return (-50);/case 7: return (-400);/; s/case 8: return (-30);/case 8: return (-250);/' superlu_mt-4.0.0/SRC/sp_ienv.c && "
   "grep -q 'case 7: return (-400);' superlu_mt-4.0.0/SRC/sp_ienv.c && make -C superlu_mt-4.0.0 superlulib && make -j4 && test -x bin/3D-ICE-Emulator", "ice_build.log")
sh(f"git clone -q https://github.com/uvahotspot/HotSpot.git /opt/hotspot && cd /opt/hotspot && git checkout -q {V['HOTSPOT_COMMIT']} && "
   f"patch -p1 --fuzz=0 < {P}/hotspot-f18831e.patch && patch -p1 --fuzz=0 < {P}/hotspot-lu-reuse.patch && make SUPERLU=1 hotspot && test -x hotspot", "hs_build.log")
sh(f"git clone -q https://github.com/peaclab/PACT.git /opt/pact && cd /opt/pact && git checkout -q {V['PACT_COMMIT']} && "
   f"patch -p1 < {P}/pact-bb7f05a.patch && patch -p1 < {P}/pact-labels.patch", "pact_build.log")
os.environ["PATH"] = f"/opt/3d-ice/bin:/opt/hotspot:{os.environ['PATH']}"; os.environ["PACT_SRC"] = "/opt/pact/src"
os.environ["OTS_IMAGE"] = "kaggle-build"; os.environ["PYTHONPATH"] = SRC
os.chdir(SRC)
sh("python -m pytest -q -p no:cacheprovider tests/test_solvers.py", "solver_tests.log", check=False)
print(open(f"{W}/solver_tests.log").read()[-800:], flush=True)
def unit(name, f, solver):
    left = LIMIT_S - (time.time() - T0)
    if left < EST[f][solver]:
        print(f"no time for {name} x{f} {solver} ({left:.0f} s left)", flush=True); return
    cap = int(min(left, 3 * EST[f][solver]))         # one slow or hung unit cannot take the rest of the session
    r = sh(f"timeout {cap} python gates/g93/dry/floor.py {W}/floor {f} {name} {solver} {cap - 60}",
           "floor_units.log", check=False)
    print((r.stdout + r.stderr).strip().splitlines()[-1:] or ["(no output)"], flush=True)
    sh(f"python gates/g93/dry/floor_summary.py {W}/floor {W}/floor_summary.json > /dev/null", check=False)
for s_ in ("ice", "hs", "pact"):
    unit("s2", 1, s_)
r = sh(f"python gates/g93/dry/floor_summary.py {W}/floor {W}/parity.json gates/g93/dry/floor_image", check=False)
if '"parity_ok": true' not in r.stdout:
    print("parity failed: stopping before the floor units", r.stdout[-1500:], flush=True); sys.exit(0)
for n in ("s1", "s4"):
    for s_ in ("ice", "hs", "pact"):
        unit(n, 1, s_)
for n, s_ in [("s2", "ice"), ("s2", "pact"), ("s2", "hs"), ("s1", "ice"), ("s1", "pact"), ("s4", "ice"),
              ("s4", "pact"), ("s1", "hs"), ("s4", "hs")]:
    unit(n, 2, s_)
sh(f"python gates/g93/dry/floor_summary.py {W}/floor {W}/floor_summary.json", check=False)
print("total", round(time.time() - T0), "s")
