# OpenTSense G93 size probe on a Kaggle CPU session: build 3D-ICE, HotSpot and PACT from the pinned commits and
# patches (as docker/Dockerfile and Dockerfile.g94a), check the build with the solver tests, then probe S3 and S2.
import os, shutil, subprocess, sys, time, json
W = "/kaggle/working"; SRC = f"{W}/src"; T0 = time.time()
def sh(cmd, log=None, check=True):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, executable="/bin/bash")
    if log: open(f"{W}/{log}", "w").write(r.stdout + r.stderr)
    print(f"[{time.time() - T0:7.0f} s] rc {r.returncode}: {cmd[:120]}", flush=True)
    if check and r.returncode: print((r.stdout + r.stderr)[-3000:], flush=True); sys.exit(1)
    return r
inp = [os.path.join("/kaggle/input", d) for d in os.listdir("/kaggle/input")]
print("inputs", inp, flush=True)
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
   f"patch -p1 < {P}/hotspot-f18831e.patch && make SUPERLU=1 hotspot && test -x hotspot", "hs_build.log")
sh(f"git clone -q https://github.com/peaclab/PACT.git /opt/pact && cd /opt/pact && git checkout -q {V['PACT_COMMIT']} && "
   f"patch -p1 < {P}/pact-bb7f05a.patch && patch -p1 < {P}/pact-labels.patch", "pact_build.log")
os.environ["PATH"] = f"/opt/3d-ice/bin:/opt/hotspot:{os.environ['PATH']}"; os.environ["PACT_SRC"] = "/opt/pact/src"
os.chdir(SRC)
sh("python -m pytest -q -p no:cacheprovider tests/test_solvers.py", "solver_tests.log", check=False)
print(open(f"{W}/solver_tests.log").read()[-1500:], flush=True)
out = open(f"{W}/size_probe_kaggle.jsonl", "w")
for stack, cell in (("s2", 250), ("s3", 500)):
    for solver in ("ice", "hs", "pact"):
        r = sh(f"timeout 10800 python gates/g93/dry/size_probe.py {stack} {cell} {solver} /tmp/probe_{stack}_{solver}", check=False)
        line = (r.stdout.strip().splitlines() or [""])[-1]
        if not line.startswith("{"):
            line = json.dumps(dict(stack=stack, solver=solver, ok=False, exit=r.returncode, tail=(r.stdout + r.stderr)[-500:]))
        print(line, flush=True); out.write(line + "\n"); out.flush()
print("total", round(time.time() - T0), "s")
