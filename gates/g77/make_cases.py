"""G77 case sets: G84's case maker with another seed and noise level (G77 draft, open choice 1).

G84's pilot set (seed 84, sigma 0.1 K) was seen before G77's bars were fixed, so the registered run needs sets the bars
were not tuned on. This runs `gates/g84/make_cases.py` unchanged except for its SEED and NOISE constants; the seed
changes the program split, the workload draws and the sensor noise. G84's own record is untouched.

Usage (from the repo root): python gates/g77/make_cases.py OUT.npz --seed 77 --noise 0.05
"""
import argparse
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def load_g84():
    spec = importlib.util.spec_from_file_location("g84_make_cases", os.path.join(HERE, "..", "g84", "make_cases.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--noise", type=float, required=True, help="sensor noise sigma, K")
    a = ap.parse_args(argv)
    if a.seed == 84:
        raise SystemExit("seed 84 is G84's pilot set, already seen; pick another")
    if not a.noise > 0:
        raise SystemExit("noise must be positive")
    g84 = load_g84()
    g84.SEED, g84.NOISE = a.seed, a.noise
    g84.main(a.out)


if __name__ == "__main__":
    main()
