"""G94 transient cases: power sequences {die: (n_slots, ny, nx)} on G93a's stacks (draft.md, "Cases").

- step:  G71's maps of one seed switched on at t = 0 and held (n_slots slots);
- pulse: the same maps on for `on_slots` slots, then off;
- programs (stacks with a CPU die: 3d, 3d_bottom): the CPU die runs the G81b Embench programs one after another in a
  seeded order, each held for `dwell_slots` slots at G84's construction for one segment per program (block power
  CPU_BLOCK_W x the program's mean dynamic power / the median, spread over the 4 x 4 regions by its whole-run toggle
  shares, G84's dark power elsewhere); the TPU die holds G71's map of the seed.
"""
import json
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STACKS = {"3d": ("g71_3d.yaml", {"top": "tpu", "bot": "cpu"}),               # G93a's names and configs
          "25d_regions": ("g93a_25d_regions.yaml", {"chiplets": "m25"}),
          "3d_bottom": ("g93a_3d_bottom.yaml", {"top": "tpu", "bot": "cpu"})}

CPU_BLOCK_W = 1.0719      # G84's CPU block power (gates/g84/make_cases.py; G84 is recorded and frozen)


def names(stack_name):
    """The cases each stack runs: programs wherever there is a CPU die to drive."""
    return ("step", "pulse") + (("programs",) if "cpu" in STACKS[stack_name][1].values() else ())


def builders(stack_name, seed, S):
    """{case: () -> power sequence} for one stack (built only when called), lengths from the settings S."""
    build = {"step": lambda: step(stack_name, seed, S["step_slots"]),
             "pulse": lambda: pulse(stack_name, seed, S["pulse_slots"], S["pulse_on_slots"]),
             "programs": lambda: programs(seed, S["dwell_slots"], stack_name)[0]}
    return {c: build[c] for c in names(stack_name)}


def maps(stack_name, seed):
    Z = np.load(os.path.join(ROOT, "gates", "g71", "inputs", "maps.npz"))
    return {d: Z[f"{k}_s{seed}"] for d, k in STACKS[stack_name][1].items()}


def step(stack_name, seed, n_slots):
    return {d: np.repeat(M[None], n_slots, 0) for d, M in maps(stack_name, seed).items()}


def pulse(stack_name, seed, n_slots, on_slots):
    P = step(stack_name, seed, n_slots)
    for v in P.values():
        v[on_slots:] = 0.0
    return P


def programs(seed, dwell_slots, stack_name="3d"):
    """(power, order): the CPU sequence on a stack with a CPU die ("bot") and the program order."""
    g81b = json.load(open(os.path.join(ROOT, "gates", "g81b", "record", "result.json")))["programs"]
    scaled = sorted(p for p in g81b if p != "idle_pass1" and "dyn_W" in g81b[p])     # G84's set, idle included
    med = np.median([g81b[p]["dyn_W"]["mean"] for p in scaled])
    order = list(np.random.default_rng(seed).permutation([p for p in scaled if p != "idle"]))
    Z = np.load(os.path.join(ROOT, "gates", "g71", "inputs", "maps.npz"))
    act = Z["act3"]
    (r0, c0), (r1, c1) = np.argwhere(act).min(0), np.argwhere(act).max(0) + 1
    dark = np.where(act, 0.0, 0.4 / (~act).sum())                       # as G84: 0.4 W outside the block
    bs = r1 - r0
    cpu = []
    for p in order:
        X = np.loadtxt(os.path.join(ROOT, "gates", "g81b", "runs", "main", p, "timeline.csv"), delimiter=",")[:, 1:]
        share = X.sum(0).reshape(4, 4) / X.sum()
        M = dark.copy()
        M[r0:r1, c0:c1] += np.kron(share, np.ones((bs // 4, bs // 4))) / (bs // 4) ** 2 * (
            CPU_BLOCK_W * g81b[p]["dyn_W"]["mean"] / med)
        cpu += [M] * dwell_slots
    tpu = maps(stack_name, seed)["top"]
    return {"top": np.repeat(tpu[None], len(cpu), 0), "bot": np.array(cpu)}, order
