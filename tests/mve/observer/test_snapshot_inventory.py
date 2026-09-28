"""WO-1b prospective contracts; no browser/network/model calls."""

from copy import deepcopy
import numpy as np
import pytest
from mve.observer import snapshot_inventory as inv, snapshot_blocks as blocks
from mve.observer import power


def test_frozen_inventory_counts_disjoint_and_replication_guard():
    plan = inv.load()
    assert len(plan["blocks"]) == 140
    assert len(inv.jobs(plan)) == 280
    assert plan["go2"]["K"] == 20
    for module in inv.MODULES:
        assert (
            sum(c["module"] == module and not c["contrast"] for c in plan["clusters"])
            == 5
        )
    for block in plan["blocks"]:
        if block["partition"] == "R":
            with pytest.raises(ValueError, match="replication"):
                inv.observer_block(plan, block["id"], purpose="tuning")
            with pytest.raises(ValueError, match="replication"):
                inv.observer_block(plan, block["id"], purpose="observer")
    assert inv.validate(plan) == plan


@pytest.mark.parametrize(
    "kind", ["seed", "interval", "digest", "donor", "development", "role", "power"]
)
def test_invalid_inventory_fails_closed(kind):
    plan = deepcopy(inv.load())
    a, b = plan["blocks"][:2]
    if kind == "seed":
        b["seed"] = a["seed"]
    elif kind == "interval":
        b["source"] = deepcopy(a["source"])
    elif kind == "digest":
        b["data_sha256"] = a["data_sha256"]
    elif kind == "donor":
        plan["clusters"][1]["blocks"]["donor"] = plan["clusters"][0]["blocks"]["donor"]
    elif kind == "development":
        a["source"]["start"] = 1
    elif kind == "role":
        a["partition"] = "R"
    else:
        plan["power_sha256"] = "0" * 64
    plan["sha256"] = inv.seal(plan)["sha256"]
    with pytest.raises(ValueError):
        inv.validate(plan)


def test_numeric_generators_reproduce_and_count():
    for module in inv.MODULES:
        kinds = (
            ["GUE", "GOE", "Poisson"]
            if module in inv.ZERO
            else ["random-prime", "Cramer", "shuffled-index", "primes"]
        )
        for kind in kinds:
            x = blocks.sample(kind, module, 64, 1729, 200001, 240001)
            assert np.array_equal(
                x, blocks.sample(kind, module, 64, 1729, 200001, 240001)
            )
            assert len(x) == (64 if module in inv.ZERO else 65)
            assert np.isfinite(x).all()
    with pytest.raises(ValueError):
        blocks.sample("bad", "spectral", 64, 1, 0, 1)


def test_power_rows_cover_every_contrast_at_actual_n():
    plan = inv.load()
    study = inv.load_power()
    for b in plan["blocks"]:
        if b["role"] == "contrast":
            row = inv.power_row(b, study)
            assert row["upper_power"] >= 0.8
            assert row["n"] == b["n"]
    a = power.prospective_study(repeats=20, sizes=(32, 64))
    assert a == power.prospective_study(repeats=20, sizes=(32, 64))


def test_cache_integrity_and_high_height_precision(tmp_path):
    import hashlib

    (tmp_path / "PROVENANCE.txt").write_text("fixture")
    (tmp_path / "zeros3").write_text("header\n1.00000001\n1.00000003\n")
    sha = hashlib.sha256((tmp_path / "zeros3").read_bytes()).hexdigest()
    (tmp_path / "SHA256SUMS").write_text(sha + "  zeros3\n")
    assert blocks.verify_cache(tmp_path)["files"]["zeros3"] == sha
    assert blocks.read_zeros(tmp_path, "zeros3").tolist() == [1.00000001, 1.00000003]
    (tmp_path / "zeros3").write_text("drift")
    with pytest.raises(ValueError, match="cache"):
        blocks.verify_cache(tmp_path)


def test_every_block_reproduces_without_opening_outcomes():
    plan = inv.load()
    assert inv.build() == plan
    assert len({b["seed"] for b in plan["blocks"]}) == 140
    for b in plan["blocks"]:
        raw = inv.block_data(plan, b, purpose="capture")
        assert raw
    first = plan["blocks"][0]
    assert inv.observer_block(plan, first["id"], purpose="observer") == first
    with pytest.raises(ValueError):
        inv.observer_block(plan, first["id"], purpose="capture")
    changed = deepcopy(first)
    changed["seed"] += 1
    with pytest.raises(ValueError):
        inv.block_data(plan, changed, purpose="capture")
    changed = deepcopy(plan)
    changed["blocks"][0]["data_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        inv.block_data(changed, changed["blocks"][0], purpose="capture")
    with pytest.raises(ValueError):
        inv.validate(changed)
    with pytest.raises(ValueError):
        inv.power_row(first, inv.load_power())
    with pytest.raises(ValueError):
        blocks.sample("primes", "polar-ulam", 64, 1, 200001, 200002)
    with pytest.raises(ValueError):
        power.prospective_study(repeats=1)


def test_contrast_check_on_simulation_not_held_out_inventory():
    block = next(b for b in inv.load()["blocks"] if b["generator"] == "GOE")
    numeric = {"source_gaps": blocks.sample("GOE", "spectral", 1024, 987654).tolist()}
    result = power.prospective_check(block, numeric, inv.load_power())
    assert result["detected"] and not result["inferential"]
    numeric["source_gaps"] = [1, 2, 3]
    with pytest.raises(ValueError):
        power.prospective_check(block, numeric, inv.load_power())
