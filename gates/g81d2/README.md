# G81d2: sustained CPU→accelerator offload, G51's data layout kept · PASS (conv's (v) narrow) (10 Nov 2026)

Registration: `registration.md`. Run: `run.sh`, detached in WSL, started 04:02 on 10 Nov. mlp1 and conv ran together (1 h 49 min and 1 h 21 min), then matmul (32 min). Build: `pad mm=4032,conv=4000,mlp1=4000`, LAYOUT_OK. Output: `runs/main/` (logs, `result.json`, `timelines.npz`, generated sources, `sha256.txt`). Scored with `../g81d/evaluate.py`.

An earlier launch at 03:45 was lost when Windows ran out of memory and WSL restarted at about 03:50, three minutes in. Nothing was measured; its logs are in `~/g81d/aborted_main2_0350/`.

| Bar | mm (K = 100) | conv (K = 4) | mlp1 (K = 3) |
|---|---|---|---|
| (v) iteration 1 within 1% of G51 | 37,213 vs 37,227 (−0.04%) ✓ | 2,218,347 vs 2,197,389 (**+0.95%**, narrow) ✓ | 4,314,352 vs 4,314,792 (−0.01%) ✓ |
| (a) rc 0, all stamps, ≥ 99% windows | 99.97% ✓ | 99.99% ✓ | 99.99% ✓ |
| (b) steady iterations: duration ≤ 1%, duty ≤ 0.01 | 0.52%, busy 0.0018, retire 0.0012 ✓ | 0.03%, 0, 0 ✓ | 0.21%, 0, 0 ✓ |

conv's +0.95% is expected in sign. G51 read the end cycle right after `tiled_conv_auto` returned, while each G81d2 iteration ends with `gemmini_fence()`, so it also waits for Gemmini to drain.

## Reported
| Workload | Steady Gemmini busy | Steady Rocket retire | r(retire, busy), 1,000-cycle windows | Iteration 1 busy / retire |
|---|---|---|---|---|
| mm | 0.993 | 0.022 | −0.88 | 0.969 / 0.030 |
| conv | 0.972 | 0.049 | −0.78 | 0.971 / 0.049 |
| mlp1 | 0.999 | 0.006 | −0.58 | 0.999 / 0.006 |

- **Predictions:**
  - right: conv and mlp1 are busy ≥ 0.9 and retire ≤ 0.1; r is negative for conv and mlp1;
  - **wrong:** "matmul lower". Matmul keeps Gemmini busy 99.3% of the time; its command issue overlaps the accelerator's work.
- **Under sustained offload, "one die at a time" is nearly total:** the accelerator works more than 97% of the time and the CPU retires instructions in at most 5% of cycles. The negative r comes from short CPU bursts that issue commands while Gemmini briefly idles.
- **Cold start:** only matmul's first iteration differs (busy 0.969 vs 0.993); conv and mlp1 are steady from iteration 1.
- **Alignment sensitivity** (G81d iteration 1 vs G81d2, the same code apart from layout): conv −8.46%, mm +0.01%, mlp1 −0.05%. Only conv's buffer changed its 64-byte alignment in G81d.
- Gaps between iterations are inside the stamped durations (loop overhead plus fence), and (b) bounds them.
- **Deliverable:** `runs/main/timelines.npz`, one steady period per workload (retire and busy per 1,000-cycle window) for a family gate to use. No power or temperature was computed here.
