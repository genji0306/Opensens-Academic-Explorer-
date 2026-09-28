"""Offline review regressions; all artifact writes stay in pytest temporary roots."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from mve.observer import snapshot_batch as batch, snapshot_blocks as blocks
from mve.observer import snapshot_inventory as inv


@pytest.fixture
def plan():
    return json.loads((inv.ROOT / inv.PLAN).read_text())


@pytest.mark.parametrize("purpose", ["observer", "tuning", "analysis", "invalid"])
def test_replication_materialization_refuses_before_source_read(
    plan, monkeypatch, purpose
):
    block = next(b for b in plan["blocks"] if b["partition"] == "R")
    monkeypatch.setattr(blocks, "read_zeros", lambda *a: pytest.fail("R read"))
    for call in (
        lambda: blocks.numeric(block, purpose=purpose),
        lambda: inv.block_data(plan, block, purpose=purpose),
    ):
        with pytest.raises(ValueError):
            call()


def test_materialization_requires_explicit_purpose(plan):
    block = plan["blocks"][0]
    with pytest.raises(TypeError):
        blocks.numeric(block)
    with pytest.raises(TypeError):
        inv.block_data(plan, block)


def test_replication_capture_still_reproduces(plan):
    block = next(
        b for b in plan["blocks"] if b["partition"] == "R" and b["generator"] == "GUE"
    )
    assert inv.block_data(plan, block, purpose="capture") == inv.encoded(
        blocks.numeric(block, purpose="capture")
    )


@pytest.mark.parametrize(
    "population,key,field",
    [
        ("zeta-zero-index", "zero_indices_through", "index_start"),
        ("integer-index", "integer_indices_through", "start"),
    ],
)
def test_development_boundary_even_if_layout_changes(
    plan, monkeypatch, population, key, field
):
    block = next(b for b in plan["blocks"] if b["source"]["population"] == population)
    block["source"][field] = plan["development"][key]
    plan = inv.seal(plan)
    expected = deepcopy(plan)
    for k in ("sha256", "cache", "power_sha256"):
        expected.pop(k)
    for b in expected["blocks"]:
        b["data_sha256"] = None
    monkeypatch.setattr(inv, "layout", lambda: expected)
    with pytest.raises(ValueError, match="development"):
        inv.validate(plan)


def test_power_row_requires_gue_null(plan):
    study = inv.load_power()
    block = next(b for b in plan["blocks"] if b["role"] == "contrast")
    inv.power_row(block, study)["null"] = "GOE"
    with pytest.raises(ValueError, match="powered"):
        inv.power_row(block, study)


@pytest.fixture
def freeze(tmp_path, monkeypatch, plan):
    monkeypatch.setattr(inv, "ROOT", tmp_path)
    files = {}
    for category in (
        "observer_prompts",
        "contract",
        "power_study",
        "thresholds",
        "runner_source",
    ):
        path = tmp_path / (category + ".txt")
        path.write_text(category)
        files[category] = {path.name: batch.s.sha256(path)}
    record = inv.seal({"manifest_sha256": plan["sha256"], "files": files})
    lock = tmp_path / "mve/DEPS.lock"
    lock.parent.mkdir()
    lock.write_text(json.dumps({"packets": {"WO-1b": {"go2_freeze": record}}}))
    return lock, record


@pytest.mark.parametrize("purpose", ["observer", "analysis"])
@pytest.mark.parametrize("kind", ["png", "data"])
def test_replication_load_requires_freeze_before_artifact_read(
    plan, tmp_path, monkeypatch, purpose, kind
):
    block = next(b for b in plan["blocks"] if b["partition"] == "R")
    monkeypatch.setattr(
        batch, "completed", lambda *a: pytest.fail("artifact read before freeze")
    )
    loader = inv.observer_png if kind == "png" else inv.snapshot_data
    with pytest.raises(ValueError, match="replication.*freeze"):
        loader(plan, block["id"], 0, tmp_path, purpose=purpose)


@pytest.mark.parametrize(
    "category",
    ["observer_prompts", "contract", "power_study", "thresholds", "runner_source"],
)
def test_freeze_recomputed_at_each_load(plan, freeze, tmp_path, monkeypatch, category):
    lock, record = freeze
    block = next(b for b in plan["blocks"] if b["partition"] == "R")
    inv.require_go2_freeze(plan)
    (tmp_path / (category + ".txt")).write_text("drift")
    monkeypatch.setattr(
        batch, "completed", lambda *a: pytest.fail("artifact read before freeze")
    )
    for loader in (inv.observer_png, inv.snapshot_data):
        with pytest.raises(ValueError, match="freeze"):
            loader(plan, block["id"], 0, tmp_path, purpose="analysis")


@pytest.mark.parametrize(
    "mutation",
    [
        "digest",
        "missing_category",
        "empty_category",
        "manifest",
        "path",
        "missing_file",
    ],
)
def test_invalid_freeze_refuses(plan, freeze, mutation):
    lock, record = freeze
    if mutation == "digest":
        record["sha256"] = "0" * 64
    else:
        if mutation == "missing_category":
            del record["files"]["thresholds"]
        elif mutation == "empty_category":
            record["files"]["thresholds"] = {}
        elif mutation == "manifest":
            record["manifest_sha256"] = "0" * 64
        elif mutation == "path":
            record["files"]["thresholds"] = {"../outside": "0" * 64}
        else:
            record["files"]["thresholds"] = {"absent": "0" * 64}
        record = inv.seal(record)
    lock.write_text(json.dumps({"packets": {"WO-1b": {"go2_freeze": record}}}))
    with pytest.raises(ValueError, match="freeze"):
        inv.require_go2_freeze(plan)


@pytest.mark.parametrize("oversized", ["data", "pair", "receipts"])
def test_save_pass_refuses_total_before_first_write(tmp_path, oversized):
    from tests.mve.observer.test_snapshot_batch import fake_packet

    packet = fake_packet({}, b"{}")
    if oversized == "data":
        packet["data"] = b"x" * inv.SNAPSHOT_CAP
    elif oversized == "pair":
        packet["blind"] = b"x" * (inv.SNAPSHOT_CAP // 2)
    else:
        packet["state"] = {"large": "x" * inv.SNAPSHOT_CAP}
    with pytest.raises(ValueError, match="envelope"):
        batch.save_pass(tmp_path, 0, packet)
    assert list(tmp_path.iterdir()) == []


def test_batch_json_reuses_portable_path_guard(tmp_path):
    with pytest.raises(ValueError, match="nonportable"):
        batch.write(tmp_path / "receipt.json", {"nested": ["/" + "Users/private/file"]})
    assert not (tmp_path / "receipt.json").exists()


@pytest.mark.parametrize(
    "used,free,incoming",
    [
        (199 * 1024**2, 6 * 1024**3, 2 * 1024**2),
        (0, 5 * 1024**3 - 1, 1),
    ],
)
def test_wo1b_archive_guard_precedes_any_extraction(
    tmp_path, monkeypatch, used, free, incoming
):
    monkeypatch.setattr(batch.storage, "tree_bytes", lambda _: used)
    monkeypatch.setattr(batch.storage.shutil, "disk_usage", lambda _: (10**12, 0, free))
    monkeypatch.setattr(
        batch.s, "archive_repo", lambda *a: pytest.fail("archive started")
    )
    with pytest.raises(batch.storage.DiskLimitError):
        batch.archive_repo(Path("source"), "atlas", tmp_path / "stage", tmp_path)
    assert not (tmp_path / "stage").exists()


@pytest.mark.parametrize("purpose", ["observer", "analysis"])
def test_valid_freeze_delivers_verified_r_artifacts(
    plan, freeze, tmp_path, monkeypatch, purpose
):
    from tests.mve.observer.test_snapshot_batch import fake_packet, finish_fixture

    study = json.loads((Path(__file__).resolve().parents[3] / inv.POWER).read_text())
    monkeypatch.setattr(inv, "load_power", lambda: study)
    job = next(
        j
        for j in inv.jobs(plan)
        if j["block"]["partition"] == "R" and j["block"]["generator"] == "GUE"
    )
    raw = inv.block_data(plan, job["block"], purpose="capture")
    folder = tmp_path / job["snapshot_id"]
    folder.mkdir()
    packet = fake_packet(job, raw)
    batch.save_pass(folder, 0, packet)
    batch.save_pass(folder, 1, packet)
    finish_fixture(folder, plan, job, packet, packet, 1)
    assert (
        inv.snapshot_data(plan, job["block"]["id"], 0, tmp_path, purpose=purpose) == raw
    )
    assert (
        inv.observer_png(plan, job["block"]["id"], 0, tmp_path, purpose=purpose)
        == packet["blind"]
    )
    # Freezing does not authorize tuning or numeric re-materialization.
    with pytest.raises(ValueError, match="replication"):
        inv.observer_block(plan, job["block"]["id"], purpose="tuning")
    with pytest.raises(ValueError, match="replication"):
        inv.block_data(plan, job["block"], purpose=purpose)
    with pytest.raises(ValueError, match="replication"):
        blocks.numeric(job["block"], purpose=purpose)


def test_delivery_rejects_arbitrary_artifact(plan, tmp_path):
    with pytest.raises(ValueError, match="artifact"):
        inv.snapshot_artifact(
            plan,
            plan["blocks"][0]["id"],
            0,
            tmp_path,
            purpose="observer",
            filename="../outside",
        )


def test_second_pass_growth_refuses_without_new_writes(tmp_path):
    from tests.mve.observer.test_snapshot_batch import fake_packet

    packet = fake_packet({}, b"{}")
    batch.save_pass(tmp_path, 0, packet)
    before = batch.s.tree_listing(tmp_path)
    packet["blind"] = b"x" * inv.SNAPSHOT_CAP
    with pytest.raises(ValueError, match="envelope"):
        batch.save_pass(tmp_path, 1, packet)
    assert batch.s.tree_listing(tmp_path) == before


def test_archive_exact_storage_boundaries_allow_delegation(tmp_path, monkeypatch):
    monkeypatch.setattr(batch.storage, "tree_bytes", lambda _: 136 * 1024**2)
    monkeypatch.setattr(
        batch.storage.shutil, "disk_usage", lambda _: (10**12, 0, 5 * 1024**3)
    )
    calls = []
    monkeypatch.setattr(batch.s, "archive_repo", lambda *args: calls.append(args))
    batch.archive_repo(Path("source"), "atlas", tmp_path / "stage", tmp_path)
    assert calls == [(Path("source"), "atlas", tmp_path / "stage", tmp_path)]


def test_png_chunk_receipt_size_is_reserved_before_write(tmp_path, monkeypatch):
    from tests.mve.observer.test_snapshot_batch import fake_packet

    packet = fake_packet({}, b"{}")
    # Numerous small chunks fit the PNG budget but their JSON receipt does not.
    packet["blind"] = (
        packet["blind"][:33] + (b"\0\0\0\0IDAT\0\0\0\0" * 20000) + packet["blind"][-12:]
    )
    monkeypatch.setattr(
        batch.s,
        "leakage_report",
        lambda *a, **kw: pytest.fail("write before envelope check"),
    )
    with pytest.raises(ValueError, match="envelope"):
        batch.save_pass(tmp_path, 0, packet)
    assert list(tmp_path.iterdir()) == []
