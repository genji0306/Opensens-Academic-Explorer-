import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from mve.errors import RecordError
from mve.record import Record
from mve.verdicts.store import apply_request
from mve.verdicts.__main__ import main
from tests.mve.test_verdict_capture import record
from tests.mve.test_verdict_labels import split_for, label
from tests.mve.test_authority import AT


def request(**kw):
    return dict(
        operation="capture",
        target="obs_1",
        verdict="confirm",
        actor="human:alice",
        from_revision=1,
        at=AT,
        **kw,
    )


def test_concurrent_stale_writers_only_one_commits(tmp_path):
    path = tmp_path / "record.json"
    path.write_text(record().to_json())
    barrier = Barrier(2)

    def writer():
        barrier.wait()
        try:
            return apply_request(path, request()).to_dict()["revision"]
        except RecordError:
            return "stale"

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: writer(), range(2)))
    assert sorted(results, key=str) == [2, "stale"]
    assert Record.from_json(path.read_text()).to_dict()["revision"] == 2


def test_failed_adoption_and_write_failure_leave_original(tmp_path, monkeypatch):
    path = tmp_path / "record.json"
    path.write_text(record().to_json())
    original = path.read_bytes()
    args = request()
    args.update(verdict="adopt", actor="model:manager")
    with pytest.raises(RecordError):
        apply_request(path, args)
    assert path.read_bytes() == original
    import os

    def fail(*args):
        raise OSError("fixture disk failure")

    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(OSError):
        apply_request(path, request())
    assert path.read_bytes() == original
    assert not list(tmp_path.glob("*.tmp"))


def test_cli_roundtrip_export_stale_and_bad_request(tmp_path, capsys):
    path, req = tmp_path / "record.json", tmp_path / "request.json"
    path.write_text(record().to_json())
    req.write_text(json.dumps(request()))
    assert main(["apply", str(path), str(req)]) == 0
    assert json.loads(capsys.readouterr().out)["revision"] == 2
    assert main(["apply", str(path), str(req)]) == 2
    assert "stale" in capsys.readouterr().err
    req.write_text("{")
    assert main(["apply", str(path), str(req)]) == 2
    assert capsys.readouterr().err
    r = label(record())
    path.write_text(r.to_json())
    frozen = split_for(r)
    sp = tmp_path / "split.json"
    sp.write_text(frozen.payload)
    args = ["export", "--split", str(sp), "--split-sha256", frozen.sha256, str(path)]
    assert main(args) == 0
    row = json.loads(capsys.readouterr().out)
    assert row["label"] == "remeasure"
    args[4] = "0" * 64
    assert main(args) == 2
    assert "hash" in capsys.readouterr().err


def test_store_edit_uses_graph_and_unknown_operation_refused(tmp_path):
    path = tmp_path / "record.json"
    path.write_text(record().to_json())
    result = apply_request(
        path,
        dict(
            operation="edit",
            actor="human:alice",
            from_revision=1,
            at=AT,
            patch=[{"op": "replace", "path": "/entities/0/geometries/0/params/0", "value": 11}],
        ),
    )
    assert not result.to_dict()["observations"][0]["valid"]
    with pytest.raises(RecordError):
        apply_request(path, {"operation": "network"})


def test_cli_verdicts_and_module_entrypoint(tmp_path, capsys):
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "mve.verdicts", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0 and "apply" in result.stdout
    path = tmp_path / "record.json"
    path.write_text(record().to_json())
    req = request()
    del req["at"]
    r = apply_request(path, req)
    frozen = split_for(r)
    sp = tmp_path / "split.json"
    sp.write_text(frozen.payload)
    assert (
        main(
            [
                "export",
                "--kind",
                "verdicts",
                "--split",
                str(sp),
                "--split-sha256",
                frozen.sha256,
                str(path),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["verdict"] == "confirm"


def test_temporary_file_creation_failure_leaves_original(tmp_path, monkeypatch):
    import tempfile

    path = tmp_path / "record.json"
    path.write_text(record().to_json())
    original = path.read_bytes()

    def fail(**kwargs):
        raise OSError("fixture temporary file creation failure")

    monkeypatch.setattr(tempfile, "NamedTemporaryFile", fail)
    with pytest.raises(OSError):
        apply_request(path, request())
    assert path.read_bytes() == original
