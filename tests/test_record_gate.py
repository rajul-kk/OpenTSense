"""record_gate.py keeps a split run's per-machine manifests and parity checks next to the verdict."""
import importlib.util
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("record_gate", os.path.join(ROOT, "scripts", "record_gate.py"))
record_gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(record_gate)


def test_split_run_keeps_every_manifest_and_parity(tmp_path, monkeypatch):
    run = tmp_path / "gates" / "gx" / "runs" / "main"
    run.mkdir(parents=True)
    names = ["result.json", "manifest.json", "manifest_kaggle_step.json", "parity_kaggle_step.json"]
    for n in names + ["unit_hs.json"]:
        (run / n).write_text(json.dumps({"n": n}))
    monkeypatch.setattr(record_gate, "ROOT", str(tmp_path))
    assert record_gate.main(["gx"]) == 0
    assert sorted(os.listdir(tmp_path / "gates" / "gx" / "record")) == sorted(names)   # bulk units stay out


def test_missing_required_file_is_reported(tmp_path, monkeypatch):
    run = tmp_path / "gates" / "gx" / "runs" / "main"
    run.mkdir(parents=True)
    (run / "manifest.json").write_text("{}")
    monkeypatch.setattr(record_gate, "ROOT", str(tmp_path))
    assert record_gate.main(["gx"]) == 1
