"""Every gate that has run keeps a complete record in the repo.

Convention (gates/README.md):
- A gate folder with a README.md has run; the README carries its verdict.
- A run gate has a registration: registration.md, or a README section headed "Registration" (G70).
- A run gate has record/result.json and record/manifest.json, or one pair per part (record/<part>/...).
  runs/ is git-ignored bulk output; scripts/record_gate.py copies the two small files into record/.
- A folder with only registration.md is registered, not run; one with draft.md is a draft. Neither needs a record.

Known gaps are listed in KNOWN_GAPS with the reason. They are recorded facts, not waivers for new gates: a gate not in
that list fails the test until its record is complete.
"""
import json
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GATES = os.path.join(ROOT, "gates")
GATE_RE = re.compile(r"^g\d+[a-z0-9]*$")

# gate -> files allowed to be missing, and why. Do not add entries for new gates.
KNOWN_GAPS = {
    "g81c": ({"manifest.json"}, "g81c.py wrote no manifest (run 9 Nov); verdict stands, see its README"),
    "g81d": ({"manifest.json"}, "run.sh wrote no manifest (run 10 Nov)"),
    "g81d2": ({"manifest.json"}, "run.sh wrote no manifest (run 10 Nov)"),
}


def gate_dirs():
    return sorted(d for d in os.listdir(GATES) if GATE_RE.match(d) and os.path.isdir(os.path.join(GATES, d)))


def is_run(gate):
    return os.path.isfile(os.path.join(GATES, gate, "README.md"))


def has_registration(gate):
    g = os.path.join(GATES, gate)
    if os.path.isfile(os.path.join(g, "registration.md")):
        return True
    with open(os.path.join(g, "README.md"), encoding="utf-8") as fh:
        return re.search(r"^#+\s.*registration", fh.read(), re.I | re.M) is not None


def record_sets(gate):
    """Folders under record/ that hold a result.json (record/ itself, or one per part)."""
    rec = os.path.join(GATES, gate, "record")
    out = []
    for dirpath, _, files in os.walk(rec):
        if "result.json" in files:
            out.append(dirpath)
    return sorted(out)


def check_gate(gate):
    """List of problems with one gate's record (empty: complete)."""
    if not is_run(gate):
        return []
    problems = []
    if not has_registration(gate):
        problems.append("no registration.md and no Registration section in README.md")
    sets = record_sets(gate)
    if not sets:
        problems.append("no record/result.json (run scripts/record_gate.py)")
    allowed = KNOWN_GAPS.get(gate, (set(), ""))[0]
    for s in sets:
        rel = os.path.relpath(s, GATES)
        try:
            with open(os.path.join(s, "result.json"), encoding="utf-8") as fh:
                json.load(fh)
        except ValueError as e:
            problems.append(f"{rel}/result.json is not valid JSON: {e}")
        if not os.path.isfile(os.path.join(s, "manifest.json")) and "manifest.json" not in allowed:
            problems.append(f"{rel}/manifest.json missing")
    return problems


def test_gates_found():
    assert len(gate_dirs()) >= 10


@pytest.mark.parametrize("gate", gate_dirs())
def test_gate_record_complete(gate):
    assert check_gate(gate) == []


def test_known_gaps_are_still_gaps():
    """An entry whose gap has been filled must be removed, so the list never hides a later regression."""
    for gate, (files, _) in KNOWN_GAPS.items():
        for s in record_sets(gate) or [os.path.join(GATES, gate, "record")]:
            for f in files:
                assert not os.path.isfile(os.path.join(s, f)), f"{gate}: {f} now exists; drop it from KNOWN_GAPS"


def test_incomplete_gate_fails(tmp_path, monkeypatch):
    """The check catches a run gate with no registration and no record."""
    g = tmp_path / "g999"
    g.mkdir()
    (g / "README.md").write_text("# G999\nVerdict: PASS\n", encoding="utf-8")
    monkeypatch.setattr(__import__(__name__), "GATES", str(tmp_path))
    problems = check_gate("g999")
    assert any("registration" in p for p in problems)
    assert any("record/result.json" in p for p in problems)
    (g / "registration.md").write_text("bar\n", encoding="utf-8")
    (g / "record").mkdir()
    (g / "record" / "result.json").write_text("{}", encoding="utf-8")
    problems = check_gate("g999")
    assert len(problems) == 1 and problems[0].endswith("manifest.json missing")
