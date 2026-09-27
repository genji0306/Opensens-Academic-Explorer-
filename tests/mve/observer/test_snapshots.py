"""WO-1 tests written before implementation; no browser or network needed."""

from copy import deepcopy
import io
import json
from pathlib import Path
import tarfile
from unittest.mock import Mock

from PIL import Image, ImageDraw, PngImagePlugin
import pytest

from mve.observer import snapshots as s


def png(text=False):
    im = Image.new("RGB", (320, 240), "#091113")
    d = ImageDraw.Draw(im)
    d.rectangle((90, 90, 140, 170), fill="#86ebc9")
    if text:
        d.text((10, 10), "GUE planted legend", fill="white")
    meta = PngImagePlugin.PngInfo()
    meta.add_text("Answer", "Poisson")
    out = io.BytesIO()
    im.save(out, format="PNG", pnginfo=meta)
    return out.getvalue()


def test_defaults_and_partition_honesty():
    assert set(s.MODULES) == {"spectral", "field-dyson", "polar-ulam", "space-08"}
    assert s.MODULES["field-dyson"]["seed"] == 20260926
    assert s.MODULES["polar-ulam"]["seed"] == 20260925
    jobs = s.capture_jobs()
    assert len(jobs) == 8
    assert all(j["role"] == "development" for j in jobs)
    assert all(not j["go2_eligible"] for j in jobs)
    assert len({j["snapshot_id"] for j in jobs}) == 8
    for j in jobs:
        twin = next(
            t for t in jobs if t["snapshot_id"] == j["control"]["twin_snapshot_id"]
        )
        assert twin["module"] == j["module"]
        assert twin["params"] == j["params"]
        assert twin["control"]["kind"] != j["control"]["kind"]


def test_png_blinding_metadata_and_region_rule():
    dirty = png(True)
    assert "tEXt" in s.png_chunks(dirty)
    clean = s.blind_png(dirty, (0, 0, 320, 240), [(0, 0, 320, 50)])
    assert set(s.png_chunks(clean)) == {"IHDR", "IDAT", "IEND"}
    s.assert_regions_clean(clean, [(0, 0, 320, 50)])
    with pytest.raises(ValueError, match="region"):
        s.assert_regions_clean(
            s.blind_png(dirty, (0, 0, 320, 240), []), [(0, 0, 320, 50)]
        )
    assert s.blind_png(dirty, (0, 0, 320, 240), [(0, 0, 320, 50)]) == clean
    for box in [(-1, 0, 10, 10), (0, 0, 400, 30), (0, 0, 0, 0)]:
        with pytest.raises(ValueError):
            s.blind_png(dirty, box, [])
    with pytest.raises(ValueError):
        s.png_chunks(b"bad")


def test_fixture_planted_caption_and_ocr(tmp_path):
    fixture = Path(__file__).parent / "snapshot_fixtures/lab.html"
    assert "GUE planted legend" in fixture.read_text()
    p = tmp_path / "crop.png"
    p.write_bytes(png(True))
    runner = Mock(return_value=Mock(stdout="GUE planted legend\n", returncode=0))
    with pytest.raises(ValueError, match="leak"):
        s.leakage_report(p, ["GUE", "prime sphere"], executable="tesseract", run=runner)
    runner.return_value.stdout = ""
    assert (
        s.leakage_report(p, ["GUE"], executable="tesseract", run=runner)["ocr"]
        == "passed"
    )
    assert s.leakage_report(p, ["GUE"], executable=None)["ocr"] == "unavailable"
    assert s.leakage_report(p, ["GUE"], executable=None)["limitation"]


def test_safe_paths(tmp_path):
    for name in ["../escape", "/etc/passwd", "a/../../b"]:
        with pytest.raises(ValueError):
            s.inside(tmp_path, name)
    (tmp_path / "link").symlink_to("/private/tmp")
    with pytest.raises(ValueError):
        s.inside(tmp_path, "link/file")
    assert s.inside(tmp_path, "a/file") == tmp_path / "a/file"


def test_disk_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(s.shutil, "disk_usage", lambda _: (10, 9, 1))
    with pytest.raises(ValueError, match="5 GiB"):
        s.disk_guard(tmp_path, 11 * 1024**2)
    monkeypatch.setattr(s.shutil, "disk_usage", lambda _: (10**11, 0, 10**11))
    monkeypatch.setattr(s, "tree_bytes", lambda _: 499 * 1024**2)
    with pytest.raises(ValueError, match="500 MiB"):
        s.disk_guard(tmp_path, 2 * 1024**2)
    s.disk_guard(tmp_path, 1)


def tar_bytes(name="dist/index.html", kind=None):
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w") as tf:
        i = tarfile.TarInfo(name)
        i.size = 2
        if kind:
            i.type = kind
            i.linkname = "/tmp/escape"
            i.size = 0
        tf.addfile(i, io.BytesIO(b"ok"))
    return out.getvalue()


def test_archive_extraction_refuses_links_escape_and_size(tmp_path):
    s.extract_archive(io.BytesIO(tar_bytes()), tmp_path, ("dist",), limit=100)
    assert (tmp_path / "dist/index.html").read_text() == "ok"
    for data in [
        tar_bytes("../escape"),
        tar_bytes("other/file"),
        tar_bytes(kind=tarfile.SYMTYPE),
        tar_bytes(kind=tarfile.LNKTYPE),
    ]:
        with pytest.raises(ValueError):
            s.extract_archive(io.BytesIO(data), tmp_path, ("dist",))
    with pytest.raises(ValueError):
        s.extract_archive(io.BytesIO(tar_bytes()), tmp_path, ("dist",), limit=1)


def test_tree_hash_includes_ignored_and_symlinks(tmp_path):
    (tmp_path / "ignored").mkdir()
    (tmp_path / "ignored/x").write_text("one")
    (tmp_path / "link").symlink_to("ignored/x")
    a = s.tree_listing(tmp_path)
    (tmp_path / "ignored/x").write_text("two")
    b = s.tree_listing(tmp_path)
    assert a != b
    assert next(x for x in a if x["path"] == "link")["link"] == "ignored/x"
    assert s.tree_bytes(tmp_path) >= 3


def make_entry(tmp_path, job):
    out = tmp_path / job["snapshot_id"]
    out.mkdir()
    full = out / "full.png"
    full.write_bytes(png())
    crop = out / "blind.png"
    crop.write_bytes(s.blind_png(png(), (0, 0, 320, 240), []))
    data = out / "data.json"
    data.write_text("[1,2,3]\n")
    return s.make_entry(
        tmp_path,
        job,
        full,
        crop,
        data,
        {"chrome": "fixture"},
        (0, 0, 320, 240),
        [],
        {"ocr": "unavailable", "limitation": "fixture"},
        ["GUE"],
    )


def test_manifest_hashes_twins_and_card_source(tmp_path):
    entries = [make_entry(tmp_path, j) for j in s.capture_jobs()[:2]]
    manifest = {"schema": s.SCHEMA, "snapshots": entries}
    s.validate_manifest(manifest, tmp_path)
    source = s.card_source(entries[0])
    assert set(source) == {"snapshot_id", "png_sha256", "data_sha256"}
    assert source["png_sha256"] == entries[0]["png_blinded"]["sha256"]
    for field in [
        "params_sha256",
        "lab_commit",
        "data_ref",
        "control",
        "png_full",
        "withheld_text",
        "renderer_versions",
    ]:
        bad = deepcopy(manifest)
        del bad["snapshots"][0][field]
        with pytest.raises(ValueError):
            s.validate_manifest(bad, tmp_path)
    bad = deepcopy(manifest)
    bad["snapshots"][0]["params"]["seed"] += 1
    with pytest.raises(ValueError):
        s.validate_manifest(bad, tmp_path)
    bad = deepcopy(manifest)
    bad["snapshots"][0]["control"]["twin_snapshot_id"] = "missing"
    with pytest.raises(ValueError):
        s.validate_manifest(bad, tmp_path)
    (tmp_path / entries[0]["data_ref"]["path"]).write_text("tampered")
    with pytest.raises(ValueError, match="hash"):
        s.validate_manifest(manifest, tmp_path)


def test_missing_data_not_checkable(tmp_path):
    entry = make_entry(tmp_path, s.capture_jobs()[0])
    entry["data_ref"]["sha256"] = None
    entry["data_ref"]["path"] = None
    entry["status"] = "not_checkable"
    with pytest.raises(ValueError):
        s.card_source(entry)


def test_index_validates_available_png_by_path(tmp_path):
    image = tmp_path / "a.png"
    image.write_bytes(png())
    entry = {
        "id": "a",
        "module": "spectral",
        "params": {},
        "capture": {
            "params_sha256": s.digest({}),
            "png": {"path": "a.png", "sha256": s.sha256(image)},
        },
    }
    index = tmp_path / "index.json"
    index.write_text(json.dumps({"snapshots": [entry]}))
    assert s.read_index(index, tmp_path)[0]["availability"] == "verified"
    image.unlink()
    assert s.read_index(index, tmp_path)[0]["availability"] == "not_in_allowed_archive"
    entry["capture"]["png"]["path"] = "../bad"
    index.write_text(json.dumps({"snapshots": [entry]}))
    with pytest.raises(ValueError):
        s.read_index(index, tmp_path)


def test_manifest_negative_guards(tmp_path):
    entries = [make_entry(tmp_path, j) for j in s.capture_jobs()[:2]]
    manifest = {"schema": s.SCHEMA, "snapshots": entries}
    mutations = [
        lambda m: m.update(schema="wrong"),
        lambda m: m.update(snapshots=[]),
        lambda m: m["snapshots"].append(deepcopy(m["snapshots"][0])),
        lambda m: m["snapshots"][0].update(go2_eligible=True),
        lambda m: m["snapshots"][0].update(lab_commit={}),
        lambda m: m["snapshots"][0]["png_full"].update(w=1),
        lambda m: m["snapshots"][0]["png_blinded"].update(caption_free=False),
        lambda m: m["snapshots"][0]["png_blinded"].update(chunks=[]),
        lambda m: m["snapshots"][0]["control"].update(kind="contrast"),
    ]
    for mutate in mutations:
        bad = deepcopy(manifest)
        mutate(bad)
        with pytest.raises(ValueError):
            s.validate_manifest(bad, tmp_path)
    bad = deepcopy(manifest)
    bad["snapshots"][0]["data_ref"].update(path=None, sha256=None)
    with pytest.raises(ValueError):
        s.validate_manifest(bad, tmp_path)
    bad["snapshots"][0]["status"] = "not_checkable"
    bad["snapshots"][0]["snapshot_sha256"] = s.snapshot_hash(bad["snapshots"][0])
    s.validate_manifest(bad, tmp_path)
    dirty = tmp_path / entries[0]["png_blinded"]["path"]
    dirty.write_bytes(png())
    entries[0]["png_blinded"]["sha256"] = s.sha256(dirty)
    with pytest.raises(ValueError, match="metadata"):
        s.validate_manifest(manifest, tmp_path)


def test_corrupt_png_and_noninteger_region():
    for data in [
        b"\x89PNG\r\n\x1a\nX",
        b"\x89PNG\r\n\x1a\n" + b"\xff\xff\xff\xffIDATxxxx",
    ]:
        with pytest.raises(ValueError):
            s.png_chunks(data)
    with pytest.raises(ValueError):
        s.blind_png(png(), (0, 0, 1.5, 2), [])
    with pytest.raises(ValueError):
        s.blind_png(png(), (0, 0, 320, 240), [(0, 0, 400, 500)])


def test_index_bad_png_hash(tmp_path):
    (tmp_path / "a.png").write_bytes(png())
    index = tmp_path / "index.json"
    index.write_text(
        json.dumps(
            {
                "snapshots": [
                    {
                        "params": {},
                        "capture": {
                            "params_sha256": "legacy",
                            "png": {"path": "a.png", "sha256": "0" * 64},
                        },
                    }
                ]
            }
        )
    )
    with pytest.raises(ValueError, match="PNG hash"):
        s.read_index(index, tmp_path)


def test_real_git_archive_and_isolation(tmp_path, monkeypatch):
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "dist").mkdir()
    (repo / "dist/index.html").write_text("fixture")
    (repo / ".gitignore").write_text("dist/ignored\n")
    subprocess.run(
        ["git", "-C", str(repo), "add", "dist/index.html", ".gitignore"], check=True
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        check=True,
    )
    commit = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()
    (repo / "dist/ignored").write_text("ignored data")
    monkeypatch.setitem(s.COMMITS, "atlas", commit)
    monkeypatch.setitem(s.PATHS, "atlas", ("dist",))
    monkeypatch.setattr(s, "disk_guard", lambda *a: None)
    before = s.isolation_state({"atlas": repo})
    out = tmp_path / "out"
    s.archive_repo(repo, "atlas", out, tmp_path)
    assert (out / "dist/index.html").read_text() == "fixture"
    assert not (out / "dist/ignored").exists()
    assert before == s.isolation_state({"atlas": repo})
    with pytest.raises(ValueError, match="new"):
        s.archive_repo(repo, "atlas", out, tmp_path)
    monkeypatch.setitem(s.COMMITS, "atlas", "0" * 40)
    with pytest.raises((ValueError, tarfile.ReadError)):
        s.archive_repo(repo, "atlas", tmp_path / "failed", tmp_path)
    (repo / "dist/ignored").write_text("changed ignored data")
    assert before != s.isolation_state({"atlas": repo})


def test_committed_small_crop_hash_and_reencoding():
    root = Path(__file__).parent / "snapshot_fixtures"
    pins = json.loads((root / "hashes.json").read_text())["blinded.png"]
    path = root / "blinded.png"
    assert path.stat().st_size < 300_000
    assert s.sha256(path) == pins["sha256"]
    assert path.read_bytes() == s.blind_png(png(True), pins["crop_box"], pins["masks"])
    assert s.png_chunks(path.read_bytes()) == pins["chunks"]
    s.assert_regions_clean(path.read_bytes(), pins["masks"])


def test_required_source_identity_and_crop_dimensions(tmp_path):
    entries = [make_entry(tmp_path, j) for j in s.capture_jobs()[:2]]
    base = {"schema": s.SCHEMA, "snapshots": entries}
    for field in ("generator", "source_block_id", "stratum", "seed"):
        bad = deepcopy(base)
        del bad["snapshots"][0]["data_ref"][field]
        with pytest.raises(ValueError):
            s.validate_manifest(bad, tmp_path)
    bad = deepcopy(base)
    bad["snapshots"][0]["status"] = "survived"
    with pytest.raises(ValueError):
        s.validate_manifest(bad, tmp_path)
    bad = deepcopy(base)
    bad["snapshots"][0]["png_blinded"]["crop_box"] = [0, 0, 300, 240]
    with pytest.raises(ValueError, match="crop dimensions"):
        s.validate_manifest(bad, tmp_path)


@pytest.mark.parametrize(
    "count,delta,passed", [(10, 9, True), (11, 9, False), (100, 8, True)]
)
def test_png_tolerance_boundaries(tmp_path, count, delta, passed):
    first, second = tmp_path / "first.png", tmp_path / "second.png"
    image = Image.new("RGBA", (100, 100), (0, 0, 0, 255))
    image.save(first)
    for x in range(count):
        # Alpha is a channel too; no RGB-only shortcut may ignore it.
        image.putpixel((x % 100, x // 100), (0, 0, 0, 255 - delta))
    image.save(second)
    result = s.compare_png(first, second)
    assert result["passed"] is passed
    assert result["max_channel_difference"] == delta
    assert result["pixels_over_threshold"] == (count if delta > 8 else 0)


def test_snapshot_and_card_identity_bind_bytes_and_tolerance(tmp_path):
    from mve.observer.card import card_hash
    from tests.mve.observer.test_cards import draft

    entry = make_entry(tmp_path, s.capture_jobs()[0])
    card = draft().to_dict()
    card["sources"] = [s.card_source(entry)]
    original_card_hash = card_hash(card)
    assert entry["snapshot_sha256"] == s.snapshot_hash(entry)
    assert card["sources"][0]["snapshot_id"] == entry["snapshot_sha256"]
    for kind in ("png_full", "png_blinded", "data_ref", "png_repeat_tolerance"):
        changed = deepcopy(entry)
        if kind == "png_repeat_tolerance":
            changed[kind]["channel_difference_threshold"] = 9
        else:
            changed[kind]["sha256"] = "a" * 64
        assert s.snapshot_hash(changed) != entry["snapshot_sha256"]
        card["sources"] = [s.card_source(changed)]
        assert card_hash(card) != original_card_hash


def test_manifest_requires_bound_tolerance(tmp_path):
    entries = [make_entry(tmp_path, j) for j in s.capture_jobs()[:2]]
    base = {"schema": s.SCHEMA, "snapshots": entries}
    for field in ("png_repeat_tolerance", "snapshot_sha256"):
        bad = deepcopy(base)
        del bad["snapshots"][0][field]
        with pytest.raises(ValueError):
            s.validate_manifest(bad, tmp_path)
    bad = deepcopy(base)
    bad["snapshots"][0]["png_repeat_tolerance"]["channel_difference_threshold"] = 9
    with pytest.raises(ValueError, match="tolerance"):
        s.validate_manifest(bad, tmp_path)
    bad = deepcopy(base)
    bad["snapshots"][0]["snapshot_sha256"] = "a" * 64
    with pytest.raises(ValueError, match="identity"):
        s.validate_manifest(bad, tmp_path)
