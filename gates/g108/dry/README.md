# G108 dry run (not scored)

| Attempt | Scope | Outcome |
|---|---|---|
| First launch | Chip 1, both offsets | Acquired a slot (its release exit code was not logged), but the launcher failed before Python scoring ([launch log](slice.launch-failed.log)); argument handling was corrected. |
| Corrected launch | Chip 1, both offsets | Slot broker refused: 4.3 GiB free, below the 2.4 GiB request plus the 2.0 GiB margin ([refusal log](slice.log)). No scoring started. |
| Slice (20 Nov, 17:07) | Chip 1, both offsets | Complete ([slice.json](slice.json)): 46.4 s, 2.06 GiB peak (2,208,481,280 B); log `slice.20261120-170737-909.log`. The launcher logged `rc=` empty (ExitCode read without a cached handle; fixed in `launch.ps1`). |
| Full dry (20 Nov, 17:10) | Chips 1-5, both offsets | Complete ([keepout.json](keepout.json)): 48.2 s, 2.06 GiB peak (2,208,784,384 B), rc=0 (`keepout.log`); chip 1 equals the slice. Results in [draft.md](../draft.md). |
| A15 rerun (20 Nov) | Chips 1-5, both offsets, updated scorer (`keepout.py` sha256 `f7bbe5ed...`) | Complete ([a15/keepout.json](a15/keepout.json)): 74.4 s, 2,208,882,688 B peak, rc=0 ([a15/keepout.log](a15/keepout.log)). Placement, all ten unit scores and the summary equal [keepout.json](keepout.json). The gated runner pins this scorer version. |

From the repository root, run the launcher in hidden Windows PowerShell:

```powershell
$launcher = (Resolve-Path 'gates/g108/dry/launch.ps1').Path
Start-Process powershell.exe -WindowStyle Hidden -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass',
    '-File', $launcher, '-Scope', 'slice', '-RamGiB', '2.4', '-Minutes', '8')
```

It only starts the dry runner after an eight-hex medium-slot grant, bounds wall time and working set, and
releases the grant on exit. The completed `slice.json` records process peak working set and wall time separately
from the progress log. Once the slice completes, choose the memory reservation from its peak and run
`-Scope full` with that reservation (the field fit and all cases are the same size in both runs; chips run
serially). The five-chip output is `keepout.json`. Check chip 1 scores and placement match the slice before
using the full dry's paired means and SEs. The launcher retains prior attempt logs on retry.

A dry JSON counts only with its launcher log ending in `rc=0` and no `launcher error` line: the child writes
`complete: true` before the launcher's final budget checks (wall time, and the peak from the child's own record).
