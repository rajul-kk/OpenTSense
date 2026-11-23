"""Build the three solvers on a Kaggle CPU session as opentsense:g94b has them (the steps of dry/kaggle_floor.py, whose
recorded run is kept as it ran): 3D-ICE with its patch and SuperLU-MT, HotSpot f18831e with the dump and lu-reuse
patches (--fuzz=0), PACT with its two patches; then tests/test_solvers.py. Versions from docker/versions.env."""
import os
import subprocess
import sys
import time

T0 = time.time()


def sh(cmd, w, log=None, check=True):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, executable="/bin/bash")
    if log:
        open(f"{w}/{log}", "a").write(r.stdout + r.stderr)
    print(f"[{time.time() - T0:7.0f} s] rc {r.returncode}: {cmd[:120]}", flush=True)
    if check and r.returncode:
        print((r.stdout + r.stderr)[-3000:], flush=True)
        sys.exit(1)
    return r


def build(src, w):
    V = dict(l.strip().split("=", 1) for l in open(f"{src}/docker/versions.env") if "=" in l and not l.startswith("#"))
    P = f"{src}/docker/patches"
    sh("apt-get update -qq && apt-get install -y -qq --no-install-recommends bison flex libopenblas-dev "
       "libsuperlu-dev libblas-dev patch", w, "apt.log")
    slu = "superlu_mt-4.0.0"
    sh(f"git clone -q https://github.com/esl-epfl/3d-ice.git /opt/3d-ice && cd /opt/3d-ice && "
       f"git checkout -q {V['ICE_COMMIT']} && patch -p1 < {P}/3d-ice-4953952.patch && "
       f"git clone -q https://github.com/xiaoyeli/superlu_mt.git {slu} && git -C {slu} checkout -q {V['SLU_COMMIT']} && "
       f"cp {P}/{slu}.make.inc {slu}/make.inc && mkdir -p {slu}/lib && "
       "sed -i 's/case 6: return (-50);/case 6: return (-400);/; s/case 7: return (-50);/case 7: return (-400);/; "
       f"s/case 8: return (-30);/case 8: return (-250);/' {slu}/SRC/sp_ienv.c && "
       f"grep -q 'case 7: return (-400);' {slu}/SRC/sp_ienv.c && make -C {slu} superlulib && make -j4 && "
       "test -x bin/3D-ICE-Emulator", w, "ice_build.log")
    sh(f"git clone -q https://github.com/uvahotspot/HotSpot.git /opt/hotspot && cd /opt/hotspot && "
       f"git checkout -q {V['HOTSPOT_COMMIT']} && patch -p1 --fuzz=0 < {P}/hotspot-f18831e.patch && "
       f"patch -p1 --fuzz=0 < {P}/hotspot-lu-reuse.patch && make SUPERLU=1 hotspot && test -x hotspot",
       w, "hs_build.log")
    sh(f"git clone -q https://github.com/peaclab/PACT.git /opt/pact && cd /opt/pact && "
       f"git checkout -q {V['PACT_COMMIT']} && patch -p1 < {P}/pact-bb7f05a.patch && "
       f"patch -p1 < {P}/pact-labels.patch", w, "pact_build.log")
    os.environ["PATH"] = f"/opt/3d-ice/bin:/opt/hotspot:{os.environ['PATH']}"
    os.environ["PACT_SRC"] = "/opt/pact/src"
    os.environ["OTS_IMAGE"] = "kaggle-build"
    os.environ["PYTHONPATH"] = src
    os.chdir(src)
    sh("python -m pytest -q -p no:cacheprovider tests/test_solvers.py", w, "solver_tests.log", check=False)
    print(open(f"{w}/solver_tests.log").read()[-800:], flush=True)
