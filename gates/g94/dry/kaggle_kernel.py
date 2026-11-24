# G94 dry: the Kaggle kernel file for HotSpot's after-5 ms floor units (pushed as the kernel's code_file with the
# opentsense-src dataset). Copies the repo from the dataset into the working directory and runs kaggle_floor_hs.py
# there at LEVEL. Two sessions: opentsense-g94-floor-l5 (LEVEL 5) and opentsense-g94-floor-l4 (LEVEL 4).
import os
import shutil
import subprocess
import sys

LEVEL = "5"
W = "/kaggle/working"
SRC = f"{W}/src"
inp = [os.path.join("/kaggle/input", d) for d in os.listdir("/kaggle/input")]
root = next(dp for d in inp for dp, dn, fn in os.walk(d) if "opentsense" in dn and "gates" in dn)
shutil.copytree(root, SRC, dirs_exist_ok=True)
os.chdir(SRC)
sys.exit(subprocess.call([sys.executable, "gates/g94/dry/kaggle_floor_hs.py", W, LEVEL]))
