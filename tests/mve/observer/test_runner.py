import copy
import json
import hashlib
from pathlib import Path
import numpy as np
import pytest
from mve.errors import RecordError
from mve.observer.card import Card, card_hash, spec_hash, digest
from mve.observer.checks import runner as r
from mve.observer.checks.calibration import procedure
from tests.mve.observer.test_cards import draft


def small_card():
    d = draft().to_dict()
    spec = d["check_spec"]
    spec["calibration"].update(replicates=3, joint_replicates=3, size_trials=3)
    spec["dependence"]["block_len"] = 12
    spec["fitting_interval"] = [0, 0.6]
    spec["replication"] = spec["replication"][:1]
    for partition in ("development", "replication"):
        for b in spec[partition]:
            path = Path(f"tests/mve/observer/fixtures/cue_{partition}.json")
            b.update(
                min_gaps=120,
                source_block_id="cue_" + partition,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            )
    spec["spec_sha256"] = spec_hash(spec)
    d["content_hash"] = card_hash(d)
    return Card.from_dict(d).transition("well_formed").transition("frozen")


def loader(block):
    path = Path("tests/mve/observer/fixtures") / (block["source_block_id"] + ".json")
    raw = path.read_bytes()
    d = json.loads(raw)
    return dict(
        values=d["values"], sha256=hashlib.sha256(raw).hexdigest(), height=d["height"]
    )


def test_runner_freeze_stages_denominators_and_binding():
    with pytest.raises(RecordError, match="freeze"):
        r.run_stage(draft(), 1, lambda b: pytest.fail("read before freeze"))
    card = small_card()
    first = r.run_stage(card, 1, loader)
    assert first["status"] == "preliminary" and not first["inferential"]
    card = card.transition("preliminary")
    second = r.run_stage(card, 2, loader)
    assert second["blocks"][0]["ks"]["fit_size"] == 40
    assert second["blocks"][0]["baselines"]["gaudin"]["simulation_size"] == 120
    result = r.combine_stages(card, first, second)
    assert result["status"] == "inconclusive" and result["label"] == "nominal"
    checked = card.transition("checked:inconclusive", receipt=result)
    assert checked.to_dict()["artifacts"][0]["receipt"]["status"] == "inconclusive"
    bad = copy.deepcopy(first)
    bad["revision"] = 0
    with pytest.raises(RecordError, match="stale"):
        r.combine_stages(card, bad, second)
    bad = copy.deepcopy(second)
    bad["blocks"][0]["data_sha256"] = "a" * 64
    with pytest.raises(RecordError, match="partition"):
        r.combine_stages(card, first, bad)
    with pytest.raises(RecordError, match="hash"):
        r.run_stage(card, 2, lambda b: dict(loader(b), sha256="a" * 64))
    too_small = r.run_stage(card, 2, lambda b: dict(loader(b), values=[0.5, 1, 1.5]))
    assert too_small["blocks"][0]["status"] == "inconclusive"
    assert r.combine_stages(card, first, too_small)["status"] == "inconclusive"


def test_unfolding_offset_precision_and_validation():
    x = np.array([100.0, 101.0, 102.0])
    assert len(r.unfold(x, "smooth_count")) == 2
    high = r.unfold(x, "local_density_offsets", base=10**21)
    assert high == pytest.approx(np.log(1e21 / (2 * np.pi)) / (2 * np.pi))
    assert r.unfold([0.5, 1.5], "already_unfolded").sum() == 2
    for values, method, base in [
        ([2, 1, 3], "smooth_count", 0),
        ([0, 1, 2], "smooth_count", 0),
        (x, "local_density_offsets", 0),
        (x, "bad", 0),
    ]:
        with pytest.raises(RecordError):
            r.unfold(values, method, base=base)


def test_validation_bound_to_every_setting_and_known_null():
    spec = small_card().to_dict()["check_spec"]
    assert not r.verify_calibration(None, spec, 120, None)
    spec["calibration"].update(replicates=4000, joint_replicates=4000)
    config = procedure(120, 3, 12, 4000, 0.6, 4000, 0.01)
    val = dict(
        validated=True,
        null="CUE_copula_Planck_marginal",
        procedure=config,
        procedure_sha256=digest(config),
        kill_rule=spec["kill_rule"],
        trials=2000,
        upper95=0.009,
    )
    assert r.verify_calibration(val, spec, 120, val["null"])
    assert not r.verify_calibration(val, spec, 121, val["null"])
    assert not r.verify_calibration(val, spec, 120, "zeta")
    val["trials"] = 20
    assert not r.verify_calibration(val, spec, 120, val["null"])


def test_cli_card_and_output_exclusive(tmp_path):
    from mve.observer.__main__ import main

    target = tmp_path / "new.json"
    assert (
        main(
            [
                "card",
                "new",
                "tests/mve/observer/fixtures/H0.json",
                "--output",
                str(target),
            ]
        )
        == 0
    )
    d = json.loads(target.read_text())
    assert d["status"] == "draft" and d["revision"] == 1
    with pytest.raises(FileExistsError):
        main(
            [
                "card",
                "new",
                "tests/mve/observer/fixtures/H0.json",
                "--output",
                str(target),
            ]
        )


def test_gaudin_stage_is_nominal_and_model_matches_primary():
    card = small_card()
    d = card.to_dict()
    d["primary_statistic"] = "gaudin_ks"
    d["check_spec"]["model"] = "gaudin"
    d["check_spec"]["spec_sha256"] = spec_hash(d["check_spec"])
    d["content_hash"] = card_hash(d)
    receipt = r.run_stage(Card.from_dict(d), 1, loader)
    assert receipt["blocks"][0]["ks"]["model"] == "gaudin"
    assert receipt["blocks"][0]["ks"]["refits"] == 0
    assert receipt["blocks"][0]["label"] == "nominal"
    d["primary_statistic"] = "unsupported"
    d["content_hash"] = card_hash(d)
    with pytest.raises(RecordError, match="primary"):
        r.run_stage(Card.from_dict(d), 1, loader)
