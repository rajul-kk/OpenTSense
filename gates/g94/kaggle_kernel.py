# G94 gated run: the Kaggle kernel file for the HotSpot units (pushed as the kernel's code_file with the
# opentsense-src dataset). Copies the repo from the dataset into the working directory and runs kaggle_gate_hs.py
# there for SESSION. Two kernels: opentsense-g94-gate-step (SESSION "step") and opentsense-g94-gate-rest ("rest").
import os
import shutil
import subprocess
import sys

SESSION = "step"
W = "/kaggle/working"
SRC = f"{W}/src"
inp = [os.path.join("/kaggle/input", d) for d in os.listdir("/kaggle/input")]
root = next(dp for d in inp for dp, dn, fn in os.walk(d) if "opentsense" in dn and "gates" in dn)
shutil.copytree(root, SRC, dirs_exist_ok=True)
os.chdir(SRC)
sys.exit(subprocess.call([sys.executable, "gates/g94/kaggle_gate_hs.py", W, SESSION]))
