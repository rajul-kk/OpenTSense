# G93 gated run: the Kaggle kernel file (pushed as the kernel's code_file with the opentsense-src dataset). Copies the
# repo from the dataset into the working directory and runs kaggle_run.py there for the units named in UNITS.
# Session A: UNITS = "s2:ice,s2:hs,s2:pact,s4:ice,s4:hs,s4:pact,s1:ice,s1:hs,s1:pact,s3:ice,s3:pact"
# Session B (S3 HotSpot) dropped by registration Amendment 1.
import os
import shutil
import subprocess
import sys

UNITS = "s2:ice,s2:hs,s2:pact,s4:ice,s4:hs,s4:pact,s1:ice,s1:hs,s1:pact,s3:ice,s3:pact"
W = "/kaggle/working"
SRC = f"{W}/src"
inp = [os.path.join("/kaggle/input", d) for d in os.listdir("/kaggle/input")]
root = next(dp for d in inp for dp, dn, fn in os.walk(d) if "opentsense" in dn and "gates" in dn)
shutil.copytree(root, SRC, dirs_exist_ok=True)
os.chdir(SRC)
sys.exit(subprocess.call([sys.executable, "gates/g93/kaggle_run.py", W, UNITS]))
