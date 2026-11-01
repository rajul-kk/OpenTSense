"""Workloads for the ASAP7 ibex and TPU power runs: host reference results, TPU stimulus, and output checks.

ibex programs (rv32imc, built from gates/g72/inputs/ibex_sw) write a checksum to 0x8000 and set the done flag at 0x8004;
`ibex_expected` recomputes each checksum on the host with the same 32-bit arithmetic as kernels.c.
The TPU testbench streams one 130-bit word {w_valid, w_data, a_valid, a_data} per cycle and logs every result row;
`tpu_stimulus` makes the stimulus and the reference rows (8x8 int8 tiles, numpy seed 36).
"""
import json
import re

import numpy as np

M32 = 0xffffffff
IBEX_KERNELS = {0: "matmul", 1: "crc32", 2: "sort", 3: "idle", 4: "sleep"}


def _matmul():
    a = [i * 7 + 3 for i in range(36)]
    b = [i * 5 + 1 for i in range(36)]
    s = 0
    for r in range(4):
        c = [sum(a[i * 6 + k] * b[k * 6 + j] for k in range(6)) & M32 for i in range(6) for j in range(6)]
        for i in range(36):
            s ^= (c[i] + r) & M32
            a[i] = c[i] & 0xff
    return s


def _crc():
    buf = [(i * 37 + 11) & 0xff for i in range(96)]
    c = M32
    for _ in range(3):
        for v in buf:
            c ^= v
            for _ in range(8):
                c = (c >> 1) ^ (0xedb88320 & ((-(c & 1)) & M32))
    return (~c) & M32


def _sort():
    s = 0
    for r in range(2):
        for v in sorted((((i * 2654435761 + r) & M32) >> 7) & 0xffff for i in range(48)):
            s = (s * 31 + v) & M32
    return s


def ibex_expected():
    """Checksums of kernels 0-3 as 8-digit hex; kernel 4 (sleep) never finishes and has none."""
    return {0: "%08x" % _matmul(), 1: "%08x" % _crc(), 2: "%08x" % _sort(), 3: "%08x" % 0x1d1e}


def ibex_result(log):
    """Parses the testbench's RESULT line: (checksum hex, done flag, done cycle, cycles run)."""
    m = re.search(r"RESULT checksum=([0-9a-f]+) done=(\d) done_cycle=(-?\d+) cycles=(\d+)", open(log).read())
    return (m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))) if m else None


TPU_N, TPU_CYCLES = 8, 2400


def _pack(row, w):
    return sum((int(v) & ((1 << w) - 1)) << (w * j) for j, v in enumerate(row))


def tpu_stimulus(out_dir, kinds=("W1", "W2", "W3")):
    """Writes stim_<kind>.hex and ref_<kind>.json. W1 dense random int8, W2 NN-like (50% sparse non-negative
    activations), W3 idle (all zero). The generator is shared and drawn in this order, as in G36."""
    rng = np.random.default_rng(36)
    N = TPU_N
    for kind in kinds:
        vec, ref = [], []
        while len(vec) < TPU_CYCLES:
            if kind == "W1":
                A = rng.integers(-128, 128, (N, N))
                B = rng.integers(-128, 128, (N, N))
            elif kind == "W2":
                A = np.clip(np.abs(rng.normal(0, 30, (N, N))), 0, 127).astype(int) * (rng.random((N, N)) > 0.5)
                B = np.clip(np.round(rng.normal(0, 20, (N, N))), -128, 127).astype(int)
            else:
                vec += [(0, 0, 0, 0)] * 31
                continue
            for k in range(N):  # weights, last row first
                vec.append((1, _pack(B[N - 1 - k], 8), 0, 0))
            for m in range(N):  # activation rows
                vec.append((0, 0, 1, _pack(A[m], 8)))
            vec += [(0, 0, 0, 0)] * 15  # drain
            ref += [list(map(int, A[m] @ B)) for m in range(N)]
        with open(f"{out_dir}/stim_{kind}.hex", "w", newline="\n") as f:
            for wv, wd, av, ad in vec[:TPU_CYCLES]:
                f.write("%033x\n" % ((wv << 129) | (wd << 65) | (av << 64) | ad))
        json.dump(ref, open(f"{out_dir}/ref_{kind}.json", "w"))


def tpu_check(rows_path, ref_path):
    """(rows produced, rows equal to the reference at the same position). Each row is 8 signed 32-bit lanes."""
    ref = json.load(open(ref_path))
    got = []
    for l in open(rows_path):
        v = int(l.strip(), 16)
        got.append([((v >> (32 * j)) & M32) - ((1 << 32) if (v >> (32 * j + 31)) & 1 else 0) for j in range(8)])
    return len(got), sum(r == g for r, g in zip(ref, got))
