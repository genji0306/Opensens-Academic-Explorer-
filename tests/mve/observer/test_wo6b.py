"""WO-6b acceptance; no test has a hosted transport."""

from copy import deepcopy
from datetime import datetime, timezone
import json
import numpy as np
import pytest
from mve.observer import grounded as g, pilot_b as b, power, native_nulls as native
from mve.observer import refusals as f, pilot, storage, pilot_inputs as inputs
from mve.observer import rescore

OFF = datetime(2026, 9, 28, 12, tzinfo=timezone.utc)


def obs(ident="p0:1", tag="histogram_peak"):
    return dict(id=ident, feature_tag=tag, region="whole", text="One visible peak.")


def proposal(baseline="Gaudin GUE", data="source_gaps"):
    from mve.observer.pilot_cards import proposal_fixture

    p = proposal_fixture()
    p.update(observation_ids=["p0:1"])
    p["testable_form"].update(statistic="gaudin_ks", baseline=baseline, data=data)
    return p


@pytest.mark.parametrize("label", sorted(f.LABELS))
def test_refusal_labels_and_cli_are_closed(label, monkeypatch, capsys):
    def fail(**kw):
        raise f.Refusal(label)

    monkeypatch.setattr(pilot, "execute", fail)
    with pytest.raises(SystemExit):
        pilot.main(["--dry-run"])
    assert capsys.readouterr().err == f"WO-6 refused: {label}\n"


def test_unknown_exception_and_arguments_are_sanitized(monkeypatch, capsys):
    def fail(**kw):
        raise RuntimeError("SECRET private path")

    monkeypatch.setattr(pilot, "execute", fail)
    with pytest.raises(SystemExit):
        pilot.main(["--dry-run"])
    assert capsys.readouterr().err == "WO-6 refused: internal_error\n"
    with pytest.raises(SystemExit):
        pilot.main(["--SECRET"])
    assert capsys.readouterr().err == "WO-6 refused: arguments\n"
    with pytest.raises(ValueError):
        f.Refusal("SECRET")


def test_observations_are_strict_and_scoped():
    assert g.perception({"observations": [obs()]}, 0) == [obs()]
    for change in (
        {"feature_tag": "GUE"},
        {"region": "secret"},
        {"id": "p1:1"},
        {"text": 4},
    ):
        with pytest.raises(g.Malformed):
            g.perception({"observations": [{**obs(), **change}]}, 0)
    with pytest.raises(g.Malformed):
        g.perception({"observations": [obs(), obs()]}, 0)
    assert g.repeatability([obs()], [obs("p1:1")]) == 1
    assert g.repeatability([obs()], [obs("p1:1", "void")]) == 0
    assert g.repeatability([], []) is None
    assert g.repeatability([obs()], []) == 0


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"extra": 1}, "unknown_field"),
        ({"prediction": 4}, "bad_type"),
        ({"kill_threshold": True}, "bad_type"),
        ({"claim": ""}, "bad_type"),
    ],
)
def test_malformed_reason_codes(change, reason):
    assert g.diagnose({**proposal(), **change}) == reason
    p = proposal()
    del p["claim"]
    assert g.diagnose(p) == "missing_field"
    assert g.diagnose(None) == "bad_type"
    with pytest.raises(g.Malformed, match="too_many_cards"):
        g.proposals({"cards": [proposal()] * 4})
    with pytest.raises(g.Malformed, match="not_json"):
        g.parse("{")


def test_grounding_and_exclusive_baselines():
    p, q = proposal(), proposal("Poisson")
    q["testable_form"]["statistic"] = "poisson_ks"
    rows = g.assess([p, q], [obs()], job_id="job")
    assert [r["status"] for r in rows] == ["contradictory"] * 2
    assert all(r["grounded"] for r in rows)
    q["testable_form"]["data"] = "other_data"
    assert all(
        r["status"] == "grounded" for r in g.assess([p, q], [obs()], job_id="job")
    )
    for ids in ([], ["different-job:p0:1"], ["p1:99"]):
        p["observation_ids"] = ids
        assert g.assess([p], [obs()], job_id="job")[0]["status"] == "ungrounded"
    p.pop("observation_ids")
    assert g.assess([p], [], job_id="job", legacy=True)[0]["status"] == "ungrounded"


def test_committed_rescore():
    r = rescore.build()
    assert r["hosted_calls"] == 0
    assert r["by_arm"]["real"]["malformed"] == 3
    assert r["by_arm"]["real"]["ungrounded"] == 9
    assert r["by_arm"]["real"]["contradictory"] == 2
    assert r["by_arm"]["null_twin"]["ungrounded"] == 12
    assert {x["reason"] for x in r["malformed_slots"]} == {"bad_type"}
    assert all(j["tag_jaccard"] is None for j in r["repeatability"]["jobs"].values())


@pytest.mark.parametrize("module", inputs.MODULES)
def test_native_generator_reproduces_committed_null(module):
    e = next(
        e
        for e in inputs.manifest()["snapshots"]
        if e["module"] == module and e["control"]["kind"] == "null_twin"
    )
    d = json.loads((inputs.INPUTS / e["data_ref"]["path"]).read_text())
    actual = native.snapshot(module, e["data_ref"]["seed"])
    np.testing.assert_allclose(actual, np.asarray(d["values"]), atol=2e-10, rtol=2e-10)


def test_power_deterministic_and_separates_large_contrast():
    a = power.study(ns=[32, 128], repeats=40, seed=19, modules=["spectral"])
    assert a == power.study(ns=[32, 128], repeats=40, seed=19, modules=["spectral"])
    rows = a["rows"]
    assert len(rows) == 24
    assert all(0 <= r["power"] <= 1 for r in rows)
    assert any(
        r["n"] == 128
        and r["null"] == "GUE"
        and r["alternative"] == "Poisson"
        and r["power"] >= 0.8
        for r in rows
    )
    assert any(
        r["n"] == 128
        and r["null"] == "GUE"
        and r["alternative"] == "native"
        and r["power"] < 0.8
        for r in rows
    )


def test_dry_run_and_approval(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "WORKTREE", tmp_path)
    monkeypatch.setattr(b.transport.wire, "read_key", lambda: pytest.fail("key read"))
    with pytest.raises(f.Refusal, match="owner_approval"):
        b.execute(live=True, owner_approval="2026-09-28", reviewed_head="a" * 40)
    r = b.execute(live=False, clock=lambda: OFF)
    assert r["calls"] == 24 and r["hosted_calls"] == 0
    assert r["worst_case_micro_usd"] == 147456
    assert len(r["slots"]) == 24
    assert r["budget"]["prior_micro_usd"] == 6895
    assert r["repeatability"]["by_arm"]["real"]["mean_tag_jaccard"] == 1
    assert all(s["card"]["hypothesis"]["status"] == "preliminary" for s in r["slots"])
    assert all(v["grounded"] == 12 for v in r["by_arm"].values())
    with pytest.raises(f.Refusal, match="run_exists"):
        b.execute(live=False, clock=lambda: OFF)


@pytest.mark.parametrize(
    "body,code",
    [
        ([], "bad_type"),
        ({"cards": None}, "bad_type"),
        ({"cards": [], "extra": 1}, "unknown_field"),
        ({}, "missing_field"),
    ],
)
def test_card_body_errors(body, code):
    with pytest.raises(g.Malformed, match=code):
        g.proposals(body)


def test_contract_boundaries():
    with pytest.raises(ValueError):
        g.Malformed("secret")
    for body in (
        {"observations": None},
        {"observations": [obs()] * 4},
        {"observations": [{**obs(), "text": "\n" * 80}]},
    ):
        with pytest.raises(g.Malformed, match="bad_type"):
            g.perception(body, 0)
    p = proposal()
    p["resemblance_target"] = {"target": "shape", "mapping": "curve"}
    assert g.diagnose(p) is None
    p["resemblance_target"]["mapping"] = None
    assert g.diagnose(p) == "bad_type"
    p = proposal()
    p["observation_ids"] = [9]
    assert g.diagnose(p) == "bad_type"
    with pytest.raises(g.Malformed, match="bad_type"):
        g.card_prompt([{"text": "x" * 3000}])
    worst = [
        dict(
            id=f"p{i}:{j}",
            feature_tag="density_gradient",
            region="middle_center",
            text="x" * 80,
        )
        for i in (0, 1)
        for j in (1, 2, 3)
    ]
    assert len(g.card_prompt(worst).encode()) <= 2048
    with pytest.raises(g.Malformed, match="not_json"):
        g.parse("NaN")


def test_score_and_v2_hash_binding():
    job = b.load_plan()["jobs"][0]
    observed = dict(
        proposals=[proposal()],
        observations=[obs()],
        calls=["wo6b:fixture"],
        status="ok",
        reason=None,
        prompt_sha256="a" * 64,
    )
    rows = b.score(job, observed, live=False)
    assert len(rows) == 3 and rows[1]["status"] == "empty"
    card = rows[0]["card"]
    assert g.validate_card(card) == card
    from mve.observer.card import digest

    for mutate in (
        "hash",
        "lifecycle",
        "grounding",
        "status",
        "observation",
        "unknown_id",
    ):
        bad = deepcopy(card)
        if mutate == "hash":
            bad["proposal"]["claim"] += " changed"
        elif mutate == "lifecycle":
            bad["hypothesis"]["status"] = "frozen"
        elif mutate == "grounding":
            bad["assessment"]["citations"] = ["p1:3"]
        elif mutate == "status":
            bad["status"] = (
                "contradictory" if bad["status"] != "contradictory" else "grounded"
            )
        elif mutate == "observation":
            bad["observations"][0]["feature_tag"] = "guess"
        else:
            bad["observations"][0]["id"] = "p2:1"
        if mutate != "hash":
            bad["sha256"] = digest({k: v for k, v in bad.items() if k != "sha256"})
        with pytest.raises(g.Malformed):
            g.validate_card(bad)
    with pytest.raises(g.Malformed):
        g.validate_card({})
    observed["proposals"] = [{}]
    assert b.score(job, observed, live=False)[0]["reason"] == "missing_field"


def test_power_guards_and_cli(tmp_path, monkeypatch):
    for kwargs in (
        {"repeats": 19},
        {"ns": []},
        {"ns": [10001]},
        {"modules": ["absent"]},
    ):
        with pytest.raises(ValueError):
            power.study(**kwargs)
    path = tmp_path / "power.json"
    path.write_text('{"sha256":"bad"}')
    monkeypatch.setattr(power, "OUTPUT", path)
    with pytest.raises(ValueError):
        power.load()
    monkeypatch.setattr(power, "study", lambda: dict(rows=[], seed=19))
    power.main(["--output", str(path)])
    assert json.loads(path.read_text())["seed"] == 19
    monkeypatch.setattr(rescore, "build", lambda: {"hosted_calls": 0})
    rescore.main(["--output", str(path)])
    assert json.loads(path.read_text())["hosted_calls"] == 0


def test_native_source_hash_refuses(tmp_path, monkeypatch):
    e = next(e for e in inputs.manifest()["snapshots"] if e["module"] == "spectral")
    dest = tmp_path / e["data_ref"]["path"]
    dest.parent.mkdir(parents=True)
    dest.write_text("{}")
    monkeypatch.setattr(inputs, "INPUTS", tmp_path)
    monkeypatch.setattr(inputs, "manifest", lambda: {"snapshots": [e]})
    with pytest.raises(ValueError, match="source hash"):
        native.data({"module": "spectral", "source_id": e["snapshot_id"]})


def test_actual_guards(tmp_path, monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr(storage, "WORKTREE", tmp_path)
    monkeypatch.setattr(b, "verify_pins", lambda _: None)
    monkeypatch.setattr(b, "WO6B_APPROVAL", "2030-01-01")
    with pytest.raises(f.Refusal, match="owner_approval"):
        b.execute(live=True, owner_approval="2026-09-28", reviewed_head="a" * 40)
    with pytest.raises(f.Refusal, match="review_head"):
        b.execute(live=True, owner_approval="2030-01-01", reviewed_head="HEAD")
    values = iter([b"a" * 40, b" M file"])
    monkeypatch.setattr(
        pilot.subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout=next(values))
    )
    with pytest.raises(f.Refusal, match="clean_tree"):
        b.execute(live=True, owner_approval="2030-01-01", reviewed_head="a" * 40)
    with pytest.raises(f.Refusal, match="arguments"):
        b.execute(live=False, owner_approval="2030-01-01")
    with pytest.raises(f.Refusal, match="peak_window"):
        b.execute(live=False, clock=lambda: OFF.replace(hour=7))
    with storage.lock():
        with pytest.raises(f.Refusal, match="lock_held"):
            b.execute(live=False, clock=lambda: OFF)
    monkeypatch.setattr(storage.shutil, "disk_usage", lambda _: (0, 0, 4 * 1024**3))
    with pytest.raises(f.Refusal, match="disk_free"):
        b.execute(live=False, clock=lambda: OFF)
    monkeypatch.setattr(storage.shutil, "disk_usage", lambda _: (0, 0, 10 * 1024**3))
    monkeypatch.setattr(storage, "tree_bytes", lambda _: 300 * 1024**2)
    with pytest.raises(f.Refusal, match="generated_cap"):
        b.execute(live=False, clock=lambda: OFF)


def test_pin_and_reconciliation_guards(tmp_path, monkeypatch):
    plan = b.load_plan()
    bad = deepcopy(plan)
    bad["sha256"] = "0" * 64
    with pytest.raises(f.Refusal, match="design_pin"):
        b.verify_pins(bad)
    lock = json.loads((b.ROOT / "mve/DEPS.lock").read_text())
    first = next(iter(lock["packets"]["WO-6b"]["files"]))
    lock["packets"]["WO-6b"]["files"] = {first: "0" * 64}
    dest = tmp_path / "mve/DEPS.lock"
    dest.parent.mkdir(parents=True)
    dest.write_text(json.dumps(lock))
    monkeypatch.setattr(b, "ROOT", tmp_path)
    with pytest.raises(f.Refusal, match="source_pin"):
        b.verify_pins(plan)
    monkeypatch.setattr(b.accounting, "PIN", dest)
    with pytest.raises(f.Refusal, match="reconciliation"):
        b.accounting.reconcile()


@pytest.mark.parametrize(
    "field,value,label",
    [
        ("planned_calls", 25, "call_cap"),
        ("worst_case_micro_usd", 250001, "budget_cap"),
        ("worst_case_micro_usd", 1, "budget_cap"),
    ],
)
def test_plan_caps(tmp_path, monkeypatch, field, value, label):
    plan = b.load_plan()
    plan[field] = value
    monkeypatch.setattr(storage, "WORKTREE", tmp_path)
    monkeypatch.setattr(b, "load_plan", lambda: plan)
    monkeypatch.setattr(b, "verify_pins", lambda _: None)
    with pytest.raises(f.Refusal, match=label):
        b.execute(live=False, clock=lambda: OFF)


def test_b_cli_safe(monkeypatch, capsys):
    monkeypatch.setattr(
        b,
        "execute",
        lambda **kw: dict(
            planned_calls=24, calls=24, hosted_calls=0, worst_case_micro_usd=147456
        ),
    )
    assert b.main(["--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["hosted_calls"] == 0

    def fail(**kw):
        raise f.Refusal("owner_approval")

    monkeypatch.setattr(b, "execute", fail)
    with pytest.raises(SystemExit):
        b.main(["--live"])
    assert capsys.readouterr().err == "WO-6 refused: owner_approval\n"

    def unknown(**kw):
        raise OSError("secret")

    monkeypatch.setattr(b, "execute", unknown)
    with pytest.raises(SystemExit):
        b.main(["--dry-run"])
    assert capsys.readouterr().err == "WO-6 refused: internal_error\n"


@pytest.mark.parametrize(
    "failure,expected",
    [
        ("not_json", "not_json"),
        ("missing_field", "missing_field"),
        ("too_many_cards", "too_many_cards"),
        ("overrun", None),
        ("transport", None),
    ],
)
def test_bad_observations_and_failed_attempts_keep_slots(
    tmp_path, monkeypatch, failure, expected
):
    monkeypatch.setattr(storage, "WORKTREE", tmp_path)
    original = b.fake_response

    def response(prompt, job):
        raw = json.loads(original(prompt, job))
        if failure == "overrun":
            raw["usage"]["prompt_tokens"] = 17000
        elif failure == "transport":
            raw["model"] = "wrong-model"
        else:
            raw["choices"][0]["message"]["content"] = (
                "{"
                if failure == "not_json"
                else "{}"
                if failure == "missing_field"
                else json.dumps({"cards": [{}] * 4})
                if not prompt.startswith("Pixels only.")
                else raw["choices"][0]["message"]["content"]
            )
        return json.dumps(raw).encode()

    monkeypatch.setattr(b, "fake_response", response)
    r = b.execute(live=False, clock=lambda: OFF)
    assert len(r["slots"]) == 24
    assert all(row["card"] is None for row in r["slots"])
    assert r["calls"] == (1 if failure in ("overrun", "transport") else 24)
    if expected:
        assert all(row["reason"] == expected for row in r["slots"])


def test_envelope_binds_proposal_hypothesis_and_check():
    from mve.observer.card import digest

    job = b.load_plan()["jobs"][0]
    observed = dict(
        proposals=[proposal()],
        observations=[obs()],
        calls=["wo6b:fixture"],
        status="ok",
        reason=None,
        prompt_sha256="a" * 64,
    )
    card = b.score(job, observed, live=False)[0]["card"]
    for change in (
        "claim",
        "prediction",
        "direction",
        "threshold",
        "assessment_type",
        "inference",
    ):
        bad = deepcopy(card)
        if change in ("claim", "prediction"):
            bad["proposal"][change] += "changed"
        elif change == "direction":
            bad["proposal"]["testable_form"]["direction"] = "less"
        elif change == "threshold":
            bad["proposal"]["kill_threshold"] = 0.9
        elif change == "assessment_type":
            bad["assessment"]["contradictory"] = "false"
        else:
            bad["check"]["inferential"] = True
        bad["sha256"] = digest({k: v for k, v in bad.items() if k != "sha256"})
        with pytest.raises(g.Malformed):
            g.validate_card(bad)


def test_transport_input_and_storage_labels(tmp_path):
    from mve.budget import BudgetLedger
    from mve.preflight.probe_live import price_table
    from mve.observer import pilot_transport

    with pytest.raises(f.Refusal, match="input_contract"):
        pilot_transport.request(b"not an image", "x" * 2049)
    book = BudgetLedger(tmp_path / "test.sqlite", price_table=price_table())
    job = b.load_plan()["jobs"][0]
    request = pilot_transport.request(inputs.image_bytes(job["snapshot_id"]), "fixture")
    with pytest.raises(f.Refusal, match="storage"):
        pilot_transport.dispatch(
            book,
            request,
            output=tmp_path / "outside",
            attempt="wo6b:test",
            clock=lambda: OFF,
            live=False,
            fake_raw=b"{}",
        )


def test_stage1_power_uses_declared_upper_tail_not_two_sided_discrimination():
    job = next(j for j in b.load_plan()["jobs"] if j["module"] == "spectral")
    study = deepcopy(power.load())
    for row in study["rows"]:
        row["power"] = 1.0
        row["upper_power"] = 0.0
    result = power.check(proposal(), job, study_result=study)
    assert result["status"] == "underpowered"
    assert result["power"] == 0
