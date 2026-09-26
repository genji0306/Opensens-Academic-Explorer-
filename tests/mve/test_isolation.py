import errno
import json
import sys
import pytest
from mve.evaluation.isolation import IsolationError, public_packet, run_offline


def test_allowlist_keeps_legitimate_givens_and_rejects_hidden_inputs():
    data = {
        "image": "diagram.png",
        "labels": ["A", "B"],
        "stated_givens": ["AB = 2"],
        "problem_text": "Find AB.",
    }
    result = public_packet(
        data, track="annotated_problem", task="problem_understanding"
    )
    assert result["stated_givens"] == ["AB = 2"]
    for key in (
        "answer",
        "truth_classes",
        "reference_paths",
        "generator_premises",
        "sources",
    ):
        with pytest.raises(IsolationError):
            public_packet(
                {**data, key: "SECRET"},
                track="annotated_problem",
                task="problem_understanding",
            )
    with pytest.raises(IsolationError):
        public_packet(data, track="appearance_only", task="appearance")
    for path in ("../truth.json", "/private/truth.json"):
        with pytest.raises(IsolationError):
            public_packet({"image": path}, track="appearance_only", task="appearance")


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS sandbox evidence only")
def test_real_subprocess_cannot_read_gold_or_connect(tmp_path):
    private = tmp_path / "gold"
    private.mkdir()
    gold = private / "truth.json"
    gold.write_text("SECRET GOLD")
    public = tmp_path / "public"
    public.mkdir()
    (public / "input.txt").write_text("visible fixture")
    worker = public / "worker.py"
    worker.write_text("""import json, pathlib, socket, sys
result = {'public': pathlib.Path('input.txt').read_text()}
for name, action in [('gold', lambda: pathlib.Path(sys.argv[1]).read_text()),
                     ('network', lambda: socket.create_connection(('127.0.0.1', 9), timeout=1))]:
    try:
        action(); result[name] = 'UNEXPECTED SUCCESS'
    except OSError as exc:
        result[name] = exc.errno
print(json.dumps(result))
""")
    result = run_offline(
        worker, public_dir=public, private_roots=[private], args=[str(gold)]
    )
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output == {
        "public": "visible fixture",
        "gold": errno.EPERM,
        "network": errno.EPERM,
    }
    assert "SECRET GOLD" not in result.stdout


def test_unavailable_isolation_and_overlapping_roots_fail_closed(tmp_path, monkeypatch):
    worker = tmp_path / "worker.py"
    worker.write_text('print("must not run")')
    with pytest.raises(IsolationError):
        run_offline(worker, public_dir=tmp_path, private_roots=[tmp_path])
    monkeypatch.setattr("mve.evaluation.isolation.sys.platform", "unavailable")
    with pytest.raises(IsolationError):
        run_offline(
            worker, public_dir=tmp_path, private_roots=[tmp_path.parent / "gold"]
        )


def test_public_staging_rejects_links_and_worker_timeout(tmp_path):
    private = tmp_path / "gold"
    private.mkdir()
    gold = private / "truth.json"
    gold.write_text("secret")
    public = tmp_path / "public"
    public.mkdir()
    worker = public / "worker.py"
    worker.write_text("import time; time.sleep(2)")
    link = public / "leak.json"
    link.hardlink_to(gold)
    with pytest.raises(IsolationError):
        run_offline(worker, public_dir=public, private_roots=[private])
    link.unlink()
    link.symlink_to(gold)
    with pytest.raises(IsolationError):
        run_offline(worker, public_dir=public, private_roots=[private])
    link.unlink()
    with pytest.raises(IsolationError):
        run_offline(worker, public_dir=public, private_roots=[private], timeout=0.01)
