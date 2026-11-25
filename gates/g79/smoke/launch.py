"""Run a bounded local smoke stage with the Windows slot broker and host RAM sampler."""
import argparse
import ctypes
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
G81B = ROOT / "gates/g81b/runs/main"
BROKER = Path.home() / ".looptools/slots.py"
IMAGE = "sha256:76e2685256694157a3b1937008377de4f8554be7b712776f88dbbde878716e98"
MEMORY_MIB = 2500
PROGRAMS = ("crc32", "edn", "idle")


class Memory(ctypes.Structure):
    _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
        (name, ctypes.c_uint64) for name in ("total", "free", "page", "page_free", "virtual", "virtual_free", "extended")
    ]


def memory():
    stat = Memory()
    stat.length = ctypes.sizeof(stat)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
        raise ctypes.WinError()
    return stat.total, stat.free


def inputs(stage):
    if stage == "build":
        source = json.loads((HERE / "source.json").read_text(encoding="utf-8"))
        files = [HERE / "build.sh", HERE / "regions.vh", HERE / "source.json",
                 ROOT / "gates/g81b/tb/ibex_tb_g81b.v", ROOT / "gates/g81b/tb/main.cpp"]
        for name, entry in source["files"].items():
            path = HERE / "source" / name
            if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
                raise ValueError(f"verified source changed: {name}")
    else:
        program = "crc32" if stage == "slice" else stage
        files = [HERE / "obj/simv", G81B / "sw" / f"{program}.hex", G81B / program / "run.log"]
    return {file.relative_to(ROOT).as_posix(): hashlib.sha256(file.read_bytes()).hexdigest() for file in files}


def docker_stage(stage, out, timeout_s):
    name = f"g79-smoke-{uuid.uuid4().hex[:12]}"
    command = ["docker", "run", "--rm", "--name", name, "--network", "none", "--cpus", "2",
               "--memory", f"{MEMORY_MIB}m", "--memory-swap", f"{MEMORY_MIB}m",
               "--mount", f"type=bind,source={ROOT},target=/repo,readonly",
               "--mount", f"type=bind,source={HERE},target=/smoke",
               "--workdir", f"/smoke/{out.name}", "--entrypoint", "/bin/bash", IMAGE]
    if stage == "build":
        command += ["/smoke/build.sh"]
    else:
        program = "crc32" if stage == "slice" else stage
        cap = 10_000 if stage == "slice" else 6_000_000
        command += ["-c", 'exec /smoke/obj/simv "$@"', "sim",
                    f"+hex=/repo/gates/g81b/runs/main/sw/{program}.hex", f"+max={cap}"]
    hashes = inputs(stage)
    total, free = memory()
    samples = [free]
    finished = threading.Event()

    def sample():
        while not finished.wait(0.10):
            samples.append(memory()[1])

    monitor = threading.Thread(target=sample)
    monitor.start()
    start = time.monotonic()
    rc = 1
    try:
        with (out / "run.log").open("wb") as log:
            try:
                rc = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=timeout_s,
                                    env={**os.environ, "MSYS_NO_PATHCONV": "1"}, check=False).returncode
            except subprocess.TimeoutExpired:
                subprocess.run(["docker", "stop", "--time", "1", name], capture_output=True, timeout=20, check=False)
                rc = 124
    finally:
        elapsed = time.monotonic() - start
        finished.set()
        monitor.join()
        samples.append(memory()[1])
        (out / "metrics.json").write_text(json.dumps({
            "stage": stage, "image_id": IMAGE, "returncode": rc, "wall_s": elapsed,
            "machine_total_bytes": total, "machine_start_free_bytes": free, "machine_min_free_bytes": min(samples),
            "machine_peak_used_bytes": total - min(samples), "ram_samples": len(samples),
            "container_cap_mib": MEMORY_MIB, "inputs_sha256": hashes,
        }, indent=2) + "\n", encoding="utf-8")
    print(f"{stage} rc={rc} wall={elapsed:.2f}s, machine peak used={(total - min(samples)) / 2**30:.2f} GiB")
    return rc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("build", "slice", *PROGRAMS))
    stage = parser.parse_args().stage
    if stage != "build":
        build = HERE / "build" / "run.log"
        if "BUILD_COMPLETE" not in build.read_text(encoding="utf-8", errors="replace").splitlines():
            raise SystemExit("build left no positive end marker")
    if stage in PROGRAMS and not (HERE / "slice" / "passed.txt").is_file():
        raise SystemExit("short slice must be checked before full programs")
    broker = [sys.executable, "-B", str(BROKER)]
    grant = subprocess.run([*broker, "acquire", "g79-smoke", "heavy", "2.5", "10"],
                           capture_output=True, text=True, check=False)
    lines = grant.stdout.splitlines()
    slot = lines[-1].strip() if lines else ""
    if grant.returncode or not re.fullmatch(r"[0-9a-f]{8}", slot):
        raise SystemExit(f"heavy slot refused: {grant.stdout.strip()}")
    try:
        out = HERE / stage
        out.mkdir()
        return docker_stage(stage, out, 420 if stage == "build" else 120)
    finally:
        subprocess.run([*broker, "release", slot], check=True)


if __name__ == "__main__":
    sys.exit(main())
