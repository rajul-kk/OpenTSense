"""Exercise G108's real evaluator with frozen layouts and synthetic chip scores."""
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from gates.g108 import evaluate as g108
from gates.g108 import run as runner
from gates.g108.dry import keepout

ARM = "bot2/outside_uniform"
UNIT = "indep/31"


@pytest.fixture(scope="module")
def dry():
    return runner.dry_reference()


@pytest.fixture
def synthetic(dry):
    scores = {name: dry[name] for name in ("dies", "stack", "shape", "cell_um", "split_counts", "placement")}
    scores = copy.deepcopy(scores)
    bootstrap = {"diff": 0.0, "ci95": [-0.1, 0.1], "p": 1.0, "groups": 4, "n_boot": 10000, "seed": 0}
    arm = {metric: {die: 1.0 for die in dry["dies"]} for metric in keepout.METRICS}
    arm[keepout.BOOTSTRAP] = dict.fromkeys(dry["dies"], bootstrap)
    scores.update(key={**keepout.registered_key(runner.CHIPS), "inputs_sha256": keepout.input_hashes(runner.RUN_INPUTS),
                       "runtime": dry["key"]["runtime"]},
                  complete=True, inputs_unchanged=True, units={
                      unit: copy.deepcopy({name: copy.deepcopy(arm) for name in keepout.ARMS})
                      for unit in keepout.unit_names(runner.CHIPS)
                  }, summary={"wrong_cached_summary": True})
    return scores


def write_run(path, scores):
    data = json.dumps(scores).encode()
    (path / "scores.json").write_bytes(data)
    (path / "manifest.json").write_text(json.dumps({"gate": "G108", "key": scores["key"]}), encoding="utf-8")
    digest = hashlib.sha256(data).hexdigest()
    log = path / "launch.synthetic.log"
    log.write_text(f"scores_sha256={digest}\nrc=0 slot=1234abcd release_rc=0\n", encoding="utf-8")
    return log


def test_pass_uses_per_unit_scores_at_inclusive_bar(tmp_path, synthetic):
    for chip in runner.CHIPS:
        synthetic["units"][f"indep/{chip}"][ARM]["field_model/rmse_K"]["bot"] = 1.25
    write_run(tmp_path, synthetic)
    g108.main(tmp_path)
    result = json.loads((tmp_path / "result.json").read_bytes())
    assert result["verdict"] == "PASS"
    assert result["bars"]["a"]["mean"] == 0.25
    assert result["bars"]["a"]["se"] == 0
    assert result["evaluator_sha256"] == hashlib.sha256(Path(g108.__file__).read_bytes()).hexdigest()


def test_an_early_inconclusive_result_still_names_the_evaluator(tmp_path):
    g108.main(tmp_path)
    result = json.loads((tmp_path / "result.json").read_bytes())
    assert result["verdict"] == "INCONCLUSIVE"
    assert result["evaluator_sha256"] == hashlib.sha256(Path(g108.__file__).read_bytes()).hexdigest()


def test_the_runner_preflight_reads_the_same_runtime_fields_the_scorer_records(dry):
    assert set(runner.runtime()) == set(dry["key"]["runtime"])


def test_runner_refuses_a_runtime_other_than_the_dry_records(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENBLAS_NUM_THREADS", "7")
    monkeypatch.setattr(keepout, "run_locked", lambda *a, **k: pytest.fail("scored under a drifted runtime"))
    with pytest.raises(ValueError, match="runtime"):
        runner.main(tmp_path / "run")


def test_the_scorer_pin_is_the_version_the_a15_rerun_used(dry):
    a15 = json.loads((runner.ROOT / "gates/g108/dry/a15/keepout.json").read_text(encoding="utf-8"))
    assert runner.dry_input_pins(dry)[runner.SCORER] == a15["key"]["inputs_sha256"][runner.SCORER]
    assert a15["units"] and a15["units"] == {k: v for k, v in dry["units"].items() if k in a15["units"]}
    assert a15["placement"] == dry["placement"]


@pytest.mark.parametrize(("offset", "bar"), [("indep", "a"), ("corr0.8_3mm", "b")])
def test_each_bar_fails_when_one_chips_two_site_rmse_raises_the_mean(tmp_path, synthetic, offset, bar):
    synthetic["units"][f"{offset}/31"][ARM]["field_model/rmse_K"]["bot"] = 4.0
    write_run(tmp_path, synthetic)
    result = g108.evaluate(tmp_path)
    assert result["verdict"] == "FAIL"
    assert result["bars"][bar]["mean"] == pytest.approx(0.3)
    assert result["bars"][bar]["se"] == pytest.approx(0.3)
    assert result["bars"][bar]["chip_deltas"] == [3.0] + [0.0] * 9
    assert not result["bars"][bar]["ok"]
    assert sum(x["ok"] for x in result["bars"].values()) == 1


@pytest.mark.parametrize(("path", "value", "check"), [
    (("key", "case_set_sha256"), "bad-sha", "case_set_sha256"),
    (("key", "profile"), "other", "profile"),
    (("key", "chips"), list(range(30, 40)), "chips"),
    (("key", "salt"), 108, "salt"),
    (("key", "offsets", "corr0.8_3mm"), [0.8, 2.0], "offsets"),
    (("key", "inputs_sha256", keepout.CASES), "0" * 64, "inputs_sha256"),
    (("key", "runtime", "numpy"), "1.26.4", "runtime"),
    (("complete",), False, "complete"),
    (("inputs_unchanged",), False, "inputs_unchanged"),
    (("split_counts", "train"), 239, "case_metadata"),
    (("placement", "union", 0, 1), 11, "sites_as_dry"),
    (("placement", "placement_noise_K"), 0, "sites_as_dry"),
    (("placement", "sites", ARM, 0, 1), 11, "fixed_top_sites"),
    (("placement", "sites", ARM, -1, 1), 60, "site_grid"),
    (("placement", "sites", ARM, -1, slice(None)), [1, 22, 22], "outside_eligible"),
    (("units", UNIT, ARM, "field_model/rmse_K", "bot"), float("nan"), "finite_metrics"),
    (("units", UNIT, ARM, "average/peak_err_K", "top"), "bad", "finite_metrics"),
    (("units", UNIT, ARM, keepout.BOOTSTRAP, "bot", "ci95"), [0, float("inf")], "finite_metrics"),
], ids=["case-sha", "profile", "chips", "salt", "offsets", "input-hash", "runtime", "complete", "unchanged", "split",
        "union", "placement-noise", "fixed-top", "grid", "ineligible", "nan", "text-metric", "bootstrap"])
def test_invalid_value_is_inconclusive(tmp_path, synthetic, path, value, check):
    field = synthetic
    for name in path[:-1]:
        field = field[name]
    field[path[-1]] = value
    write_run(tmp_path, synthetic)
    assert_inconclusive(tmp_path, check)


def assert_inconclusive(path, check):
    result = g108.evaluate(path)
    assert not result["checks"][check], result["checks"]
    assert result["verdict"] == "INCONCLUSIVE"
    assert "bars" not in result


def test_repeated_buried_site_is_inconclusive(tmp_path, synthetic):
    sites = synthetic["placement"]["sites"][ARM]
    sites[-1] = sites[-2]
    write_run(tmp_path, synthetic)
    assert_inconclusive(tmp_path, "buried_counts")


@pytest.mark.parametrize(("path", "check"), [
    (("key", "inputs_sha256", "gates/g108/run.py"), "inputs_sha256"),
    (("units", UNIT), "all_units"),
    (("units", UNIT, ARM), "finite_metrics"),
    (("units", UNIT, ARM, "field_model/rmse_K", "bot"), "finite_metrics"),
])
def test_missing_input_unit_arm_or_metric_is_inconclusive(tmp_path, synthetic, path, check):
    field = synthetic
    for name in path[:-1]:
        field = field[name]
    del field[path[-1]]
    write_run(tmp_path, synthetic)
    assert_inconclusive(tmp_path, check)


def test_extra_chip_is_inconclusive(tmp_path, synthetic):
    synthetic["units"]["indep/1"] = synthetic["units"][UNIT]
    write_run(tmp_path, synthetic)
    assert_inconclusive(tmp_path, "all_units")


@pytest.mark.parametrize(("name", "check"), [("manifest.json", "manifest"), ("scores.json", "scores_readable"),
                                            ("launch.synthetic.log", "launcher")])
def test_missing_run_artifact_is_inconclusive(tmp_path, synthetic, name, check):
    write_run(tmp_path, synthetic)
    (tmp_path / name).unlink()
    assert_inconclusive(tmp_path, check)


def test_bad_score_json_is_inconclusive(tmp_path):
    (tmp_path / "scores.json").write_bytes(b'{"partial":\xff')
    assert_inconclusive(tmp_path, "scores_readable")


def test_changed_dry_reference_is_inconclusive(tmp_path, synthetic, monkeypatch):
    write_run(tmp_path, synthetic)
    monkeypatch.setattr(runner, "DRY_SHA", "0" * 64)
    assert_inconclusive(tmp_path, "dry_reference")


def test_success_log_must_identify_the_exact_score_bytes(tmp_path, synthetic):
    write_run(tmp_path, synthetic)
    scores = tmp_path / "scores.json"
    scores.write_bytes(scores.read_bytes() + b"\n")
    assert_inconclusive(tmp_path, "launcher")


def test_launcher_failure_overrides_score_completion(tmp_path, synthetic):
    log = write_run(tmp_path, synthetic)
    log.write_text("launcher error: G108 run exceeded its budget\nrc=1 slot=1234abcd release_rc=0\n", encoding="utf-8")
    assert_inconclusive(tmp_path, "launcher")


def test_runner_rejects_layout_drift_before_scoring(tmp_path, dry, monkeypatch):
    cases = SimpleNamespace(sha256=lambda: keepout.G84_SHA)
    monkeypatch.setattr(keepout.CaseSet, "load", lambda _: cases)
    monkeypatch.setattr(keepout, "layouts", lambda _: ({}, None))
    monkeypatch.setattr(keepout, "score_chip", lambda *args: pytest.fail("scorer reached on layout mismatch"))
    with pytest.raises(ValueError, match="placement differs from the dry reference"):
        keepout.run((1,), tmp_path / "scores.json", reference=dry["placement"])
    assert not (tmp_path / "scores.json").exists()
