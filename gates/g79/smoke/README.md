# G79 Ibex RTL proxy smoke · FAIL

**Use the rail-telemetry fallback.** The pinned RTL built successfully, CRC32 and
EDN matched the routed Ibex, and the CRC32 activity alignment passed. The
unchanged G81b idle program trapped before its first phase marker and returned
a different checksum. The smoke required all programs, including idle, to
agree. The failed result is preserved as run. [Idle check](idle/check.json)

## Provenance and build

The original ASAP7 Ibex synthesis used the SystemVerilog directory
`flow/designs/src/ibex_sv`. The saved canonical RTLIL names
`designs/src/ibex_sv/ibex_core.sv`, and the synthesis log records the SLANG
frontend. The pinned ORFS image carries that directory and the ASAP7 Ibex
configuration. The similarly named `flow/designs/src/ibex` is absent.
[Canonical RTLIL](../../../../../_build/asap7/asap7-ibex/results/asap7/ibex/base/1_1_yosys_canonicalize.rtlil)
· [Synthesis log](../../../../../_build/asap7/asap7-ibex/logs/asap7/ibex/base/1_1_yosys_canonicalize.log)
· [ORFS image probe](provenance-probe.log) · [G72 manifest](../../g72/record/manifest.json)

All 32 files extracted from those two directories matched the corresponding
bytes at [ORFS commit f528507](https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts/commit/f52850725e4ffe4030175328aa976cd8fb4943b9).
The [source manifest](source.json) names the image, repository, matching public
commit, archive digest and per-file SHA-256. This establishes an exact source
match for these files. The image did not attest a full ORFS build commit.
The [build log](build/run.log) supplies the Verilator version (5.032) and the
`BUILD_COMPLETE` marker. The build used the original G81b testbench and C++
harness, replacing only its placement-dependent monitor include with the RTL
signal monitor. [Build inputs and pinned image](build/metrics.json)

## Program checks

Compare the full `RESULT` tuple and the ordered start, stop and phase events
with the stored G81b log. A process exit of zero alone does not satisfy this
check.

| Program | Checksum, done cycle and markers | Host wall time | Machine-wide peak used |
|---|---|---:|---:|
| CRC32 | **PASS.** `00000000`, done at 983,651, both markers equal. [Comparison](crc32/check.json) | 1.062 s | 8.78 GiB [Metrics](crc32/metrics.json) |
| EDN | **PASS.** `00000000`, done at 1,040,797, both markers equal. [Comparison](edn/check.json) | 1.031 s | 8.77 GiB [Metrics](edn/metrics.json) |
| Idle | **FAIL.** RTL `dead0002` at 1,666, no phase markers. Gate level `9c2704d8` at 370,959. The RTL log reports an illegal instruction `0x3047a073` at PC `0x00000110`. [Comparison](idle/check.json) · [RTL log](idle/run.log) | 0.344 s to the trap | 8.78 GiB [Metrics](idle/metrics.json) |

The build took 19.172 s and peaked at 9.45 GiB of whole-machine used RAM,
736.6 MiB above its starting observation. Before the full programs, a
10,000-cycle CRC32 slice passed the expected stop, first marker and timeline
checks. It took 0.484 s and peaked at 9.45 GiB of whole-machine used RAM,
1.2 MiB above its starting observation. These are sampled Windows host
figures including other processes. The start-to-peak difference is a host
observation. [Build metrics](build/metrics.json) · [Slice check](slice/check.json)
· [Slice metrics](slice/metrics.json)

## Alignment and compute

CRC32's RTL activity file and G81b's regional timeline have the same 983
full-row indices. In two 1,000-cycle G81b VCD windows, the falling-edge
cycles also match the intended rows. The four RTL interface toggle counts
agree with counts from the same signals in those VCDs, within the one
boundary transition unavailable per signal in a windowed VCD. The comparison
uses the regional totals to identify the corresponding timeline rows and
records the like-for-like signal counts separately. It checks cycle
alignment. [Alignment record](alignment.json) · [G81b timeline convention](../../g81b/regions.py)

The passing programs ran at about **0.93–1.01 million cycles per host-wall
second**, including container launch. At the G81b clock of 900 ps, a 0.5 ms
slot spans about 555,556 cycles, which costs about **0.55–0.60 s per slot**
at those measured rates. This puts RTL trace capture alone within a few
hours for a substantially longer run at similar throughput. It leaves the
cost of power labels, fitting and validation open. The idle failure blocks
the meter on the chosen workload set regardless of throughput.
[CRC32 throughput](crc32/check.json) · [EDN throughput](edn/check.json)
· [Testbench clock](../../g81b/tb/ibex_tb_g81b.v)

## Lints checked

| Lints | Application |
|---|---|
| A10, L11 | Record host whole-machine RAM and wall time. Check a short slice first and estimate slot time from passing full executions. |
| A16, A17 | Separate build, slice and program records. Keep the first failed run. Record input hashes and retain the raw logs. |
| A21, A23 | Compare with preserved gate-level results. Use G81b's clock, falling-edge sampling and row-end convention. |
| A24 | Verify the source and configuration bytes against the pinned image and public commit. Record the original firmware and testbench hashes. |
| A25 | Cite the logs, metrics and computed comparisons. |
| L5, L29, L67 | Require a build marker, complete result, ordered markers, the expected timeline rows and a harness end marker. Idle exited zero but failed comparison. |
| L24, L41, L79 | Disable Git Bash path rewriting for Docker. Acquire and validate a heavy slot without an MSYS PID and release it after each stage. |
