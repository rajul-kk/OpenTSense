# G81d: sustained CPU→accelerator offload on G51's Chipyard SoC · INCONCLUSIVE (10 Nov 2026)

Registration: `registration.md` (with the 9 Nov pre-run note). Main run: `run.sh`, detached in WSL, 9–10 Nov (mlp1 and conv together, then matmul; 2 h 06 min + 29 min). Logs and `result.json` in `runs/main/`. Re-run as **G81d2** (`../g81d2/`).

| Bar | mm (K = 100) | conv (K = 4) | mlp1 (K = 3) |
|---|---|---|---|
| (v) iteration 1 within 1% of G51 | 37,218 vs 37,227 (−0.02%) ✓ | **2,030,643 vs 2,197,389 (−7.59%) ✗** | 4,312,079 vs 4,314,792 (−0.06%) ✓ |
| (a) complete, ≥ 99% windows | rc 0, 99.97% ✓ | rc 0, 99.99% ✓ | rc 0, 99.99% ✓ |
| (b) steady iterations periodic | duration 0.33%, busy 0.0018, retire 0.0023 ✓ | 0.09%, 0, 0 ✓ | 0.16%, 0, 0 ✓ |

(v) failed on conv, so the gate is INCONCLUSIVE as registered, and the duty cycles and correlations are not used.

## Cause of the (v) failure (diagnosed 10 Nov, before any reading of the measurements)
1. The looped conv did less work, not the same work faster: Gemmini busy cycles per iteration were 1.96M against G51's 2.15M, and retired instructions about 126k against 154k.
2. Ruled out: the build environment. Rebuilding the original `conv_perf.c` today gives code, `.rodata` and section headers identical to G51's binary (the hashes differ only in metadata). Also ruled out: the regenerated `gemmini_params.h`, which equals its committed version.
3. Ruled out: the simulator. That rebuilt original, run on today's simulator, reproduces G51 exactly: 2,197,389 cycles, busy 2,154,170, retire 154,146 (`~/g81d/diag/conv_orig.log`). The simulation is deterministic.
4. **Cause: data alignment.** The static `g81d_stamp` array moved conv's 4 MB `heap` from `0x80004c48` (8 bytes past a 64-byte boundary) to `0x80004d00` (64-byte aligned). Gemmini's DMA does about 9% less work on the aligned buffer. mlp1's buffers moved by 128 bytes (same alignment), and matmul's buffers were unaffected within 0.02%.

So G51's conv phases were measured on an accidentally misaligned buffer. That is the original test's layout, and so the reference G81d must match.

## Fix for G81d2
`make_src.py --stack --pad`, `build.sh … --stack`, `layout.py`:
- the stamps live on the stack;
- `.text` is padded, in a two-pass build, so every DMA buffer lands exactly one 4 KiB page above its G51 address (same offset within the page, so the same alignment at every level up to the page);
- `layout.py --check` verifies all 18 buffers (mm 4, conv 1, mlp1 13).

## Reported for the record only (not readings; the gate is INCONCLUSIVE)
Steady-state Gemmini busy / Rocket retire / r: mm 0.993 / 0.022 / −0.87; conv 0.969 / 0.054 / −0.77; mlp1 0.999 / 0.006 / −0.55.
