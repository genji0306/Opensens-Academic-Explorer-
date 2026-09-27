import pytest
from mve.observer.design import allocate, Design
from mve.observer.metrics import sign_flip, report
from tests.mve.observer.wo45_helpers import fixture


def test_seeded_allocation_fixed_slots_exclusive_and_immutable(tmp_path):
    manifest, config = fixture(tmp_path, 4, 2)
    plan = allocate(manifest, tmp_path, config)
    d = plan.to_dict()
    assert d == allocate(manifest, tmp_path, config).to_dict()
    assert len(d["clusters"]) == 4 and len(d["jobs"]) == 32
    assert (
        len(
            {c[k] for c in d["clusters"] for k in ("discovery", "replication", "donor")}
        )
        == 12
    )
    assert all(j["slots"] == 3 for j in d["jobs"])
    assert {j["arm"] for j in d["jobs"]} == {
        "real",
        "null_twin",
        "image_free",
        "shuffled",
    }
    assert len({j["id"] for j in d["jobs"]}) == 32
    d["config"]["seed"] += 1
    assert plan.to_dict() != d
    with pytest.raises(ValueError, match="hash"):
        Design.from_dict(d)
    config["seed"] += 1
    assert (
        allocate(manifest, tmp_path, config).to_dict()["jobs"] != plan.to_dict()["jobs"]
    )


@pytest.mark.parametrize(
    "fault",
    [
        "development",
        "reuse",
        "overlap",
        "hash",
        "views",
        "slots",
        "retries",
        "generic",
        "stratum",
    ],
)
def test_design_fail_closed(tmp_path, fault):
    m, c = fixture(tmp_path)
    if fault == "development":
        m["snapshots"][0]["data_ref"]["role"] = "development"
    if fault == "reuse":
        c["strata"][0]["donors"] = c["strata"][0]["discovery"]
    if fault == "overlap":
        m["snapshots"][2]["data_ref"]["support"] = m["snapshots"][0]["data_ref"][
            "support"
        ]
    if fault == "hash":
        m["snapshots"][0]["png_blinded"]["sha256"] = "a" * 64
    if fault == "views":
        c["views"] = 2
    if fault == "slots":
        c["slots"] = 4
    if fault == "retries":
        c["retries"] = 3
    if fault == "generic":
        c["image_free"]["zero spacings"].pop()
    if fault == "stratum":
        c["strata"][0]["id"] = "wrong"
    with pytest.raises(ValueError):
        allocate(m, tmp_path, c)


def test_exact_sign_flip_and_mc():
    assert sign_flip([1] * 5, seed=1)["p"] == 1 / 32
    assert sign_flip([1, -1, 0], seed=1)["p"] == 0.75
    assert sign_flip([0] * 20, seed=1)["p"] == 1
    r = sign_flip([1] * 21, seed=1)
    assert r["draws"] == 100000 and r["p"] == 1 / 100001 and r["upper95"] > r["p"]
    assert r == sign_flip([1] * 21, seed=1)


def test_reports_keep_empty_slots_and_no_pilot_pass(tmp_path):
    m, c = fixture(tmp_path)
    plan = allocate(m, tmp_path, c)
    rows = [
        dict(job=j["id"], slot=i, card=None, checkable=False, status="empty")
        for j in plan.to_dict()["jobs"]
        for i in range(3)
    ]
    r = report(plan, rows, "model:O-DS")
    assert r["GO1"]["requested"] == 12 and r["GO1"]["well_formed"] == 0
    assert r["GO2"]["status"] == "descriptive_only" and r["GO2"]["clusters"] == 1
    assert all(v["p"] == 1 for v in r["GO2"]["comparisons"].values())
    assert r["GO2"]["by_stratum"][c["strata"][0]["id"]]["real"]["slots"] == 3
    with pytest.raises(ValueError):
        report(plan, rows[:-1], "model:O-DS")


def test_sign_flip_rejection_boundary_and_weighted_counts():
    assert sign_flip([1] * 15 + [-1] * 5, seed=1)["p"] < 0.05
    assert sign_flip([1] * 14 + [-1] * 6, seed=1)["p"] > 0.05
    assert sign_flip([3, 1, -2, 0], seed=1)["p"] == 0.375
    with pytest.raises(ValueError):
        sign_flip([0.5], seed=1)


def test_development_inputs_cannot_be_promoted(tmp_path):
    m, c = fixture(tmp_path)
    for e in m["snapshots"]:
        e["status"] = "development_only"
        e["go2_eligible"] = False
        e["data_ref"]["role"] = "development"
    c["development_blocks"] = list(
        {e["data_ref"]["source_block_id"] for e in m["snapshots"]}
    )
    with pytest.raises(ValueError, match="block reuse"):
        allocate(m, tmp_path, c)


def test_scaled_gate_needs_all_controls_and_eight_of_ten_contrasts(tmp_path):
    from mve.observer.run import make_card
    from mve.observer.card import binding

    m, c = fixture(tmp_path, 30, 2)
    for st in c["strata"]:
        st["contrast_discovery"] = st["discovery"][10:]
        st["contrast_replication"] = st["replication"][10:]
        for key in ("discovery", "replication", "donors"):
            st[key] = st[key][:10]
    plan = allocate(m, tmp_path, c)
    rows = []
    for j in plan.to_dict()["jobs"]:
        for slot in range(3):
            card = None
            if j["arm"] in ("real", "contrast") and j["view"] == 0 and slot == 0:
                card = make_card(
                    c["image_free"]["zero spacings"][0],
                    job=j,
                    plan=plan,
                    observer="model:O-DS",
                    call_ids=["fixture"],
                    slot=slot,
                )
                card = (
                    card.transition("well_formed")
                    .transition("frozen")
                    .transition("preliminary")
                )
                d = card.to_dict()
                receipt = {
                    **binding(d),
                    "spec_sha256": d["check_spec"]["spec_sha256"],
                    "status": "baseline_exceeding_survivor",
                    "inferential": True,
                }
                card = card.transition(
                    "checked:baseline_exceeding_survivor", receipt=receipt
                ).to_dict()
            rows.append(
                dict(
                    job=j["id"],
                    slot=slot,
                    card=card,
                    checkable=bool(card),
                    status="fixture",
                )
            )
    r = report(plan, rows, "model:O-DS")
    assert r["GO2"]["clusters"] == 20 and r["GO2"]["contrast_clusters"] == 10
    assert r["GO2"]["status"] == "conditional_pass"
    contrast_jobs = {j["id"] for j in plan.to_dict()["jobs"] if j["arm"] == "contrast"}
    for row in [r for r in rows if r["job"] in contrast_jobs and r["card"]][:3]:
        row["card"] = None
    assert report(plan, rows, "model:O-DS")["GO2"]["status"] == "not_established"


def test_replication_bytes_are_not_opened_during_allocation(tmp_path, monkeypatch):
    from pathlib import Path

    m, c = fixture(tmp_path)
    replication = {
        str(tmp_path / e["data_ref"]["path"])
        for e in m["snapshots"]
        if e["data_ref"]["role"] == "replication"
    }
    original = Path.open

    def guarded(path, *args, **kwargs):
        assert (
            str(path) not in replication
        ), "replication source opened before card freeze"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    assert allocate(m, tmp_path, c).to_dict()["clusters"]


def test_replication_deferral_validates_identity_and_requires_opt_in(tmp_path):
    from mve.observer.snapshots import validate_manifest

    m, c = fixture(tmp_path)
    with pytest.raises(ValueError, match="requires prospective"):
        validate_manifest(m, tmp_path, defer_replication_data=True)
    next(e for e in m["snapshots"] if e["data_ref"]["role"] == "replication")[
        "data_ref"
    ]["sha256"] = "bad"
    with pytest.raises(ValueError, match="deferred replication hash"):
        allocate(m, tmp_path, c)
