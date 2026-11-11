"""G81b: power-window start cycles for each program (Amendment 1).

Windows are 1,000 cycles and start on a multiple of 1,000, so each one is exactly one row of the activity timeline
(the row written at start + 1,000).
- Embench: the benchmark loop runs from the start marker for about LSF x (stop - start at LSF 1), both from the dry run
  (gates/g81b/dry/dry_run2.log). The predicted span is cut into 20 equal strata over its first 95% (margin for a
  loop that is not exactly linear in LSF) and one window starts at the 1,000-cycle boundary nearest each stratum's
  middle. evaluate.py checks every window lies between the real start and stop markers.
- idle: from its own window-free first pass (phase markers): one window at the middle of each of the 20 phases plus
  one window holding each of the 19 interior phase boundaries.
Usage: windows.py <dry_run2.log> <scale.txt> <idle pass-1 log> <out dir>   writes <out dir>/<prog>.txt
"""
import os
import re
import sys

N, LEN, COVER = 20, 1000, 0.95


def align(c):
    return int(round(c / LEN)) * LEN


def main(dry, scale, idle_log, out):
    os.makedirs(out, exist_ok=True)
    lsf = {a: int(b) for a, b in (l.split() for l in open(scale) if l.strip())}
    for l in open(dry):
        m = re.match(r"(\S+) wall_s=\d+ RESULT .*start=(-?\d+) stop=(-?\d+)", l)
        if not m or m.group(1) == "idle":
            continue
        b, s, e = m.group(1), int(m.group(2)), int(m.group(3))
        span = lsf.pop(b) * (e - s) * COVER
        w = [align(s + (i + 0.5) * span / N) for i in range(N)]
        assert all(w[i + 1] - w[i] >= LEN for i in range(N - 1)) and w[0] > s, (b, w)
        open(os.path.join(out, b + ".txt"), "w").write("\n".join(map(str, w)) + "\n")
        print(b, "start", s, "span", int(span), "W", w[1] - w[0], "first", w[0], "last", w[-1])
    assert not lsf, f"no dry-run result for {sorted(lsf)}"
    mk = [int(c) for c in re.findall(r"MARK phase=\d+ cycle=(\d+)", open(idle_log).read())]
    assert len(mk) == 21, f"idle: {len(mk)} phase markers, expected 21"
    mid = [align((mk[k] + mk[k + 1]) / 2 - LEN / 2) for k in range(20)]
    bnd = [mk[k] // LEN * LEN for k in range(1, 20)]          # the aligned window holding boundary k
    w = sorted(set(mid + bnd))
    assert len(w) == 39 and all(w[i + 1] - w[i] >= LEN for i in range(len(w) - 1)), w
    open(os.path.join(out, "idle.txt"), "w").write("\n".join(map(str, w)) + "\n")
    print("idle markers", mk, "windows", len(w))


if __name__ == "__main__":
    main(*sys.argv[1:5])
