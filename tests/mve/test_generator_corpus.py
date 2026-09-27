import gzip
import pytest
from mve.generator.corpus import build_corpus
from mve.generator.truth import FrozenTruth
from mve.evaluation.splits import FrozenSplit
from mve.record import Record


def test_small_corpus_is_family_split_and_keeps_gold_out_of_public(tmp_path):
    counts = {
        "development": 2,
        "retrieval": 2,
        "fit": 7,
        "calibration": 2,
        "sealed": 2,
    }
    report = build_corpus(tmp_path / "corpus", counts=counts, code_sha="a" * 40)
    assert report["counts"] == counts
    assert report["acceptance"] == "fixture_only"
    root = tmp_path / "corpus"
    split = FrozenSplit.load(
        (root / "private/split.json").read_text(),
        expected_sha256=report["split_sha256"],
    )
    assert len(split.manifest()["items"]) == 15
    families = {}
    for row in report["items"]:
        families.setdefault(row["family"], set()).add(row["split"])
        private = root / "private" / row["id"]
        payload = gzip.decompress((private / "truth.json.gz").read_bytes()).decode()
        assert FrozenTruth.load(
            payload, expected_sha256=row["truth_sha256"]
        ).require_fit()
        record = Record.from_json((private / "record.json").read_text())
        assert record.to_dict()["image"]["truth"]["split"] == row["split"]
        assert (
            next(r["split"] for r in split.manifest()["items"] if r["id"] == row["id"])
            == row["split"]
        )
        assert set(p.name for p in (root / "public" / row["id"]).iterdir()) == {
            "image.png"
        }
    assert all(len(splits) == 1 for splits in families.values())
    from mve.generator.receipts import write_receipts
    import json

    first, second = write_receipts(
        root, tmp_path / "generation.json", tmp_path / "audit.json"
    )
    assert first["cross_split_coordinate_collisions"] == 0
    assert second["records_validated"] == 15
    assert json.loads((tmp_path / "audit.json").read_text()) == second
    manifest_path = root / "private/manifest.json"
    saved = json.loads(manifest_path.read_text())
    saved["cross_split_coordinate_collisions"] = 9
    manifest_path.write_text(json.dumps(saved))
    with pytest.raises(ValueError, match="recomputed"):
        write_receipts(
            root, tmp_path / "bad-generation.json", tmp_path / "bad-audit.json"
        )
    with pytest.raises(FileExistsError):
        build_corpus(root, counts=counts, code_sha="a" * 40)


def test_corpus_counts_must_represent_all_reserved_families(tmp_path):
    with pytest.raises(ValueError):
        build_corpus(tmp_path / "bad", counts={"fit": 1}, code_sha="a" * 40)
