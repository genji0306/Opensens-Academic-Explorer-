"""WO-6c tests: development-only fixtures, no prospective materialization."""

from types import SimpleNamespace
from mve.observer import (
    feature_power as fp,
    capture_c as cap,
    render_c as rc,
    rescore_c,
)
from mve.observer import (
    storage,
    snapshot_batch as batch,
    snapshot_render as sr,
)
from mve.observer.card import digest

from copy import deepcopy
from io import BytesIO
import json
import numpy as np
import pytest
from PIL import Image
from mve.observer import comparative as c, development_c as dev, features as f
from mve.observer import power, pilot_c, pilot_c_accounting as accounting
from mve.observer.refusals import Refusal


def observation(side="A", tag="modality_x", ident="p0:1"):
    return dict(
        id=ident, side=side, feature_tag=tag, region="whole", text="Two distinct peaks."
    )


def proposal(side="A", tag="modality_x"):
    return dict(
        claim="This side has more modes.",
        side=side,
        feature_tag=tag,
        data="source_gaps",
        observation_ids=["p0:1"],
    )


def test_contract_and_side_grounding():
    obs = [observation()]
    assert c.perception({"observations": obs}, 0) == obs
    assert c.grounded(proposal(), obs)
    for side in ("B", "both"):
        assert not c.grounded(proposal(), [observation(side)])
    assert not c.grounded({**proposal(), "observation_ids": ["foreign:p0:1"]}, obs)
    assert not c.grounded(proposal(), [observation(tag="reflection_x")])
    for tag in (
        "outline",
        "curve_shape",
        "histogram_tail",
        "symmetry_axis",
        "panel_layout",
    ):
        with pytest.raises(ValueError):
            c.perception({"observations": [observation(tag=tag)]}, 0)
    with pytest.raises(ValueError):
        c.perception({"observations": obs * 2}, 0)
    assert len(c.card_prompt(obs).encode()) <= 2048


def test_features_known_patterns():
    x = np.linspace(-1, 1, 1000)
    mono = np.sin(np.linspace(0, 2 * np.pi, 1000)) * 0.12
    bimodal = np.r_[mono[:500] - 0.6, mono[500:] + 0.6]
    assert f.value(mono[:, None], "modality_x", (-1, 1)) == 1
    assert f.value(bimodal[:, None], "modality_x", (-1, 1)) == 2
    assert f.value(x[:, None], "reflection_x", (-1, 1)) > 0.99
    assert f.value((x * 0.2 + 0.7)[:, None], "reflection_x", (-1, 1)) < 0.1
    assert (
        f.value((np.linspace(0, 1, 1000) ** 3)[:, None], "density_linear_x", (0, 1))
        > 0.8
    )
    with pytest.raises(ValueError):
        f.value(np.array([[np.nan]]), "modality_x", (-1, 1))


def test_exported_coordinates_and_data_mapping():
    assert np.allclose(
        f.ulam(np.arange(1, 10)),
        [[0, 0], [1, 0], [1, 1], [0, 1], [-1, 1], [-1, 0], [-1, -1], [0, -1], [1, -1]],
    )
    for module in dev.MODULES:
        a = dev.original(module, "real")
        points, support, field = f.coordinates(module, a)
        assert len(points) > 80 and np.isfinite(points).all()
        assert field == ("source_gaps" if module in dev.ZERO else "display_coordinates")
        if module in dev.ZERO:
            assert points.shape[1] == 1
        else:
            assert points.shape[1] == 2


def test_register_and_sealed_order():
    register = dev.build_register()
    dev.validate_register(register)
    assert len(register["nulls"]) == 8
    assert len({r["seed"] for r in register["nulls"]}) == 8
    assert all(r["role"] == "development" for r in register["nulls"])
    bad = deepcopy(register)
    bad["nulls"][0]["seed"] = 28000000
    with pytest.raises(ValueError):
        dev.validate_register(bad)
    jobs = dev.jobs(register)
    assert len(jobs) == 8 and {j["pair_type"] for j in jobs} == {
        "real-null",
        "null-null",
    }
    assert jobs == dev.jobs(register)
    for j in jobs:
        assert set(j["sealed"]) == {"A", "B"}
        assert not any(
            t in c.PERCEPTION_PROMPT
            for t in ("real-null", "null-null", "seed", "spectral")
        )


def test_composite():
    png = BytesIO()
    Image.new("RGB", (640, 400), "red").save(png, format="PNG")
    raw = c.composite(png.getvalue(), png.getvalue())
    with Image.open(BytesIO(raw)) as im:
        assert im.size == (1024, 352)
    req = pilot_c.request(raw, c.PERCEPTION_PROMPT)
    assert req.manifest()["image_count"] == 1 and req.max_input_tokens == 16384


def test_live_locked_before_any_work(monkeypatch):
    monkeypatch.setattr(pilot_c, "load_plan", lambda: pytest.fail("live touched input"))
    with monkeypatch.context() as m:
        m.setattr(pilot_c, "WO6C_APPROVAL", None)
        with pytest.raises(Refusal, match="owner_approval"):
            pilot_c.execute(live=True, owner_approval="2026-09-29", reviewed_head="a" * 40)
    assert pilot_c.WO6C_APPROVAL == "2026-09-29"
    with pytest.raises(Refusal, match="owner_approval"):
        pilot_c.execute(live=True, owner_approval="2026-09-28", reviewed_head="a" * 40)


def test_reconciliation():
    r = accounting.build()
    assert r["prior_micro_usd"] == 16339
    assert r["remaining_micro_usd"] == 19983661
    assert len(r["report"]["attempts"]) == 49


def test_deterministic_small_power():
    a = power.comparative_study(repeats=20, modules=("spectral",))
    b = power.comparative_study(repeats=20, modules=("spectral",))
    assert a == b
    assert a["alpha"] == 0.05 and a["rows"]
    assert all(0 <= r["power"] <= 1 and 0 <= r["size"] <= 1 for r in a["rows"])
    assert {r["sample"] for r in a["rows"]} == {"one", "two"}


def seal(r):
    return {**r, "sha256": digest({k: v for k, v in r.items() if k != "sha256"})}


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "WORKTREE", tmp_path)
    monkeypatch.setattr(batch, "ROOT", tmp_path)
    monkeypatch.setattr(cap, "ROOT", tmp_path)
    return tmp_path


def test_numerics_negatives_and_direction():
    x = np.linspace(0.1, 2, 100)[:, None]
    y = x * 1.5
    value, side = f.two(x, y, "spacing_ks", (0, 3))
    assert value > 0 and side == "B"
    assert f.two(y, x, "spacing_ks", (0, 3))[1] == "A"
    assert f.two(x, x, "spacing_ks", (0, 3)) == (0, None)
    for tag in f.TAGS[:-1]:
        p = np.column_stack((x[:, 0] - 1, x[:, 0] - 1))
        z = f.alternative(p, tag, (-1, 1))
        assert z.shape == p.shape
        assert np.isfinite(f.value(z, tag, (-1, 1)))
        assert f.two(p, p, tag, (-1, 1))[1] is None
    for p in ([], [[1]], [[float("inf")]] * 4):
        with pytest.raises(ValueError):
            f.checked(p)
    for tag in ("bad", "spacing_ks", "reflection_y"):
        with pytest.raises(ValueError):
            f.value(x, tag, (0, 3))
    with pytest.raises(ValueError):
        f.value(x + 10, "reflection_x", (0, 3))
    with pytest.raises(ValueError):
        f.coordinates("bad", {"values": [1, 2, 3, 4]})
    with pytest.raises(ValueError):
        f.coordinates("space-08", {"values": [1, 2, 3, 4], "options": {"alpha": 2}})
    with pytest.raises(ValueError):
        f.coordinates("space-08", {"values": [1, 1, 3, 4]})
    assert (
        f.value(np.tile(np.arange(16) + 0.5, 10)[:, None], "density_linear_x", (0, 16))
        == 0
    )


def test_contract_negatives_and_envelope():
    for obs in (
        None,
        [observation()] * 4,
        [{**observation(), "extra": 1}],
        [{**observation(), "id": "p1:1"}],
        [{**observation(), "text": "x" * 65}],
        [{**observation(), "text": "界" * 64}],
    ):
        with pytest.raises(ValueError):
            c.perception({"observations": obs}, 0)
    for p in (
        {**proposal(), "side": "both"},
        {**proposal(), "data": "pixels"},
        {**proposal(), "observation_ids": [3]},
        {**proposal(), "observation_ids": ["x"] * 7},
        {**proposal(), "claim": ""},
    ):
        with pytest.raises(ValueError):
            c.validate(p)
    with pytest.raises(ValueError):
        c.card_prompt([observation()] * 30)
    obs = [observation()]
    p = proposal()
    check = dict(
        status="checked",
        inferential=False,
        power=1,
        detected=True,
        side="A",
        value=1,
        p_value=0.01,
        alpha=0.05,
        power_study_sha256="a" * 64,
        n_a=89,
        n_b=89,
        tag="modality_x",
        data="source_gaps",
        data_sha256="b" * 64,
        sample="two",
    )
    for patch, status in [
        ({}, "separating"),
        ({"side": "B"}, "wrong-side"),
        ({"detected": False, "p_value": 0.8}, "non-separating"),
        ({"power": 0.7}, "underpowered"),
    ]:
        card = c.envelope({"id": "j"}, p, obs, {**check, **patch})
        assert card["status"] == status
        c.validate_card(card)
    card = c.envelope(
        {"id": "j"}, p, obs, dict(status="unavailable", inferential=False)
    )
    c.validate_card(card)
    bad = deepcopy(card)
    bad["status"] = "separating"
    with pytest.raises(ValueError):
        c.validate_card(bad)
    bad = deepcopy(card)
    bad["proposal"]["side"] = "both"
    with pytest.raises(ValueError):
        c.validate_card(bad)
    assert c.report([])["null-null"]["false_difference_rate"] is None


def test_development_fail_closed(monkeypatch):
    r = dev.build_register()
    for mutate in (
        lambda r: r["nulls"][0].update(interval=[200000, 250000]),
        lambda r: r.update(study_seeds=[28000000, 28000001]),
        lambda r: r.update(purpose="other"),
    ):
        bad = deepcopy(r)
        mutate(bad)
        with pytest.raises(ValueError):
            dev.validate_register(bad)
    monkeypatch.setattr(dev, "PROSPECTIVE_ZERO_INTERVALS", ((1, 4),))
    with pytest.raises(ValueError):
        dev.validate_register(r)
    for args in [("bad", "real"), ("spectral", "D")]:
        with pytest.raises(ValueError):
            dev.original(*args)
    with pytest.raises(ValueError):
        dev.null_data("spectral", 28000000)
    with pytest.raises(ValueError):
        dev.data({"module": "spectral", "sealed": {"A": "R"}}, "A")
    original = dev.inputs.manifest()
    bad = deepcopy(original)
    bad["snapshots"][0]["data_ref"]["role"] = "D"
    monkeypatch.setattr(dev.inputs, "manifest", lambda: bad)
    with pytest.raises(ValueError):
        dev.original("spectral", "real")
    bad["snapshots"][0]["data_ref"]["role"] = "development"
    bad["snapshots"][0]["data_ref"]["sha256"] = "x"
    with pytest.raises(ValueError):
        dev.original("spectral", "real")


def test_checks_match_only_exact_power_row(monkeypatch):
    a = {"values": np.linspace(0.1, 2, 89).tolist()}
    row = dict(
        module="spectral",
        tag="modality_x",
        sample="two",
        n_a=89,
        n_b=89,
        calibration=[0] * 39,
        power=0.9,
    )
    study = {"rows": [row], "sha256": "c" * 64}
    result = fp.check("spectral", "modality_x", "source_gaps", a, a, study)
    assert not result["detected"] and result["side"] is None
    assert (
        fp.check("spectral", "modality_y", "source_gaps", a, a, study)["status"]
        == "unavailable"
    )
    assert (
        fp.check("spectral", "modality_x", "pixels", a, a, study)["status"]
        == "unavailable"
    )
    assert (
        fp.check("spectral", "modality_x", "source_gaps", a, None, study)["status"]
        == "unavailable"
    )
    row.update(sample="one", n_b=None)
    assert (
        fp.check("spectral", "modality_x", "source_gaps", a, None, study)["sample"]
        == "one"
    )
    row.update(
        tag="spacing_ks", reference=f.coordinates("spectral", a)[0][:, 0].tolist()
    )
    assert (
        fp.check("spectral", "spacing_ks", "source_gaps", a, None, study)["value"] == 0
    )
    with pytest.raises(ValueError):
        fp.study(repeats=1)
    assert fp.rank_p([0] * 39, 1) == 0.025
    # Native fixed-count conditional sample: no prospective seed or block.
    p, s = fp.sample(
        "polar-ulam",
        len(dev.null_data("polar-ulam", dev.STUDY_START)["values"]),
        dev.STUDY_START,
    )
    assert p.shape[1] == 2

    class Empty:
        def __init__(self, seed):
            pass

        def uniform(self, n):
            return np.ones(n)

    monkeypatch.setattr(fp.native, "Mulberry", Empty)
    with pytest.raises(ValueError):
        fp.sample("polar-ulam", 10, dev.STUDY_START)


def png():
    im = Image.new("RGB", (640, 400), "#091113")
    im.putpixel((1, 1), (255, 0, 0))
    im.putpixel((2, 2), (0, 255, 0))
    out = BytesIO()
    im.save(out, format="PNG")
    return out.getvalue()


def fake_packet(j):
    return dict(
        full=png(),
        blind=png(),
        data=j["raw"],
        crop=[0, 0, 640, 400],
        masks=[],
        state={},
        versions={},
    )


def test_renderer_patches_routes_and_crop(tmp_path):
    for name, patches in rc.PATCHES.items():
        # Existing WO-1/WO-1b transforms supplied with exact anchors too.
        source = "\n".join(old for old, new in sr.PATCHES.get(name, []))
        extras = []
        after = sr.transform(name, source)
        for old, new in sr.BLOCK_PATCHES.get(name, []):
            if old not in after:
                extras.append(old)
        source += "\n" + "\n".join(extras)
        after = sr.block_transform(name, sr.transform(name, source))
        source += "\n" + "\n".join(old for old, new in patches if old not in after)
        result = rc.transform(name, source)
        assert all(new in result for old, new in patches)
        with pytest.raises(ValueError):
            rc.transform(name, "drift")
    assert rc.crop("spectral", png()) == png()
    with Image.open(BytesIO(rc.crop("field-dyson", png()))) as im:
        assert im.size == (320, 400)
    route = SimpleNamespace(
        abort=lambda: events.append("abort"), fulfill=lambda **kw: events.append(kw)
    )
    events = []
    handle = rc.handler(tmp_path)
    for url, method in [
        ("http://mve.invalid/x", "GET"),
        ("https://mve.invalid/x", "POST"),
        ("https://other/x", "GET"),
        ("https://mve.invalid/missing", "GET"),
    ]:
        handle(route, SimpleNamespace(url=url, method=method))
    assert events == ["abort"] * 4
    (tmp_path / "a.js").write_text("const a=1;")
    handle(route, SimpleNamespace(url="https://mve.invalid/a.js", method="GET"))
    assert events[-1]["body"] == b"const a=1;"
    (tmp_path / "index.html").write_text("<html>")
    handle(route, SimpleNamespace(url="https://mve.invalid/", method="GET"))
    assert events[-1]["status"] == 200


def test_capture_plan_and_delivery(sandbox, monkeypatch):
    p = cap.plan()
    assert len(p["jobs"]) == 16
    for j in p["jobs"]:
        assert j["block"]["role"] == "development"
        assert (
            j["block"]["data_sha256"]
            == __import__("hashlib")
            .sha256(cap.capture_data(j["module"], j["source"]))
            .hexdigest()
        )
    job = dev.jobs(dev.load())[0]
    with pytest.raises(ValueError):
        cap.image(job, "A")
    monkeypatch.setattr(batch, "completed", lambda *a: True)
    folder = storage.local(
        cap.BASE / "snapshots" / cap.digest_id(job["module"], job["sealed"]["A"])
    )
    folder.mkdir(parents=True)
    (folder / "blind-0.png").write_bytes(png())
    assert cap.image(job, "A") == png()


@pytest.fixture
def capture_env(sandbox, monkeypatch):
    args = SimpleNamespace(
        batch=0,
        worker=False,
        prepare_only=True,
        output=None,
        atlas="atlas",
        lab="lab",
        chrome="unused",
        timeout_per_pass=300,
    )
    monkeypatch.setattr(cap.s, "isolation_state", lambda repos: {"unchanged": True})
    monkeypatch.setattr(
        batch,
        "archive_repo",
        lambda repo, name, dest, generated: dest.mkdir(parents=True),
    )
    monkeypatch.setattr(cap, "check_stage", lambda stage: {"source": "fixture"})
    monkeypatch.setattr(batch.shutil, "which", lambda x: None)

    def browser(dist, out, chrome, ocr, private, *, jobs, capture):
        context = SimpleNamespace(route=lambda *a: None)
        return [capture(context, out, j, {}, None) for j in jobs]

    monkeypatch.setattr(sr, "run_browser", browser)
    monkeypatch.setattr(
        sr, "capture_block", lambda context, root, j, versions, ocr: fake_packet(j)
    )
    monkeypatch.setenv("MVE_WO1_SANDBOX_WORKER", "1")
    monkeypatch.setenv("MVE_WO1_PRIVATE_DIR", "/private/tmp/mvewo1-fixture")

    def isolated(a, out, repos, receipt):
        workerargs = deepcopy(a)
        workerargs.worker = True
        cap.run(workerargs)

    monkeypatch.setattr(cap.old, "isolated_capture", isolated)
    return args


def test_capture_prepare_native_and_immutable(capture_env, sandbox):
    a = capture_env
    assert cap.run(a) == 0
    with pytest.raises(ValueError):
        cap.run(a)
    a.prepare_only = False
    assert cap.run(a) == 0
    p = cap.plan()
    for j in p["jobs"][:4]:
        assert batch.completed(
            storage.local(cap.BASE / "snapshots" / j["snapshot_id"]), p, j
        )
    with pytest.raises(ValueError):
        cap.run(a)
    a.batch = 1
    a.prepare_only = True
    folder = storage.local(cap.BASE / "snapshots" / p["jobs"][4]["snapshot_id"])
    folder.mkdir()
    with pytest.raises(ValueError):
        cap.run(a)


def test_capture_guards(capture_env, monkeypatch):
    a = capture_env
    a.batch = 8
    with pytest.raises(ValueError):
        cap.run(a)
    a.batch = 0
    a.worker = True
    with pytest.raises(ValueError):
        cap.run(a)
    a.output = str(cap.BASE / "prepare" / "0")
    monkeypatch.delenv("MVE_WO1_SANDBOX_WORKER")
    with pytest.raises(ValueError):
        cap.run(a)
    assert cap.main(["--batch", "0", "--timeout-per-pass", "401"]) == 2
    monkeypatch.setattr(cap, "run", lambda a: 0)
    assert cap.main(["--batch", "0", "--prepare-only"]) == 0


@pytest.fixture
def pilot_env(sandbox, monkeypatch):
    jobs = dev.jobs(dev.load())
    rows = []
    for j in jobs:
        a, b = [f.coordinates(j["module"], dev.data(j, s))[0] for s in ("A", "B")]
        rows.append(
            dict(
                module=j["module"],
                tag="modality_x",
                sample="two",
                n_a=len(a),
                n_b=len(b),
                calibration=[0] * 39,
                power=1,
            )
        )
    study = seal({"rows": rows})
    monkeypatch.setattr(fp, "load", lambda: study)
    monkeypatch.setattr(pilot_c, "verify_pins", lambda p: None)
    monkeypatch.setattr(accounting, "reconcile", accounting.build)
    return jobs


def test_pilot_full_fake_and_immutable(pilot_env, sandbox):
    from datetime import datetime, timezone

    def clock():
        return datetime(2026, 9, 28, 12, tzinfo=timezone.utc)

    r = pilot_c.execute(live=False, clock=clock)
    assert r["calls"] == 24 and r["hosted_calls"] == 0
    assert r["budget"]["prior_micro_usd"] == 16339
    assert r["budget"]["actual_new_spend_micro_usd"] == 0
    assert r["by_pair_type"]["null-null"]["false_difference_rate"] == 1
    for row in r["slots"]:
        c.validate_card(row["card"])
    reqs = list(
        sandbox.glob("mve/generated/wo6c-pilot/dry-run/attempts/*/*/request.json")
    )
    assert len(reqs) == 24
    for path in reqs:
        req = json.loads(path.read_text())
        assert req["image_count"] == 1
        assert all(
            s not in req["prompt"]
            for s in ("real-null", "null-null", "sealed", "module", "seed")
        )
    with pytest.raises(Refusal, match="run_exists"):
        pilot_c.execute(live=False, clock=clock)


def test_pilot_peak_arguments_and_main(pilot_env, monkeypatch, capsys):
    from datetime import datetime, timezone

    with pytest.raises(Refusal, match="arguments"):
        pilot_c.execute(live=False, owner_approval="wrong")
    with pytest.raises(Refusal, match="peak_window"):
        pilot_c.execute(
            live=False, clock=lambda: datetime(2026, 9, 28, 1, tzinfo=timezone.utc)
        )
    with pytest.raises(SystemExit):
        pilot_c.main(["--live"])
    assert "owner_approval" in capsys.readouterr().err
    monkeypatch.setattr(
        pilot_c,
        "execute",
        lambda **kw: {"calls": 24, "hosted_calls": 0, "worst_case_micro_usd": 147456},
    )
    assert pilot_c.main(["--dry-run"]) == 0
    monkeypatch.setattr(pilot_c, "execute", lambda **kw: {})
    with pytest.raises(SystemExit):
        pilot_c.main(["--dry-run"])
    assert "internal_error" in capsys.readouterr().err


def test_pilot_score_bad_empty_and_unavailable(pilot_env, monkeypatch):
    j = pilot_env[0]
    obs = dict(
        proposals=[
            {**proposal(), "side": "both"},
            {**proposal(), "observation_ids": []},
            {**proposal(), "data": "display_coordinates"},
        ],
        observations=[observation()],
    )
    rows = pilot_c.score(j, obs)
    assert rows[0]["status"] == "ungrounded" and rows[0]["reason"] == "malformed"
    assert rows[1]["status"] == "ungrounded" and rows[2]["status"] == "non-separating"
    assert all(
        r["card"] is None for r in pilot_c.score(j, dict(proposals=[], observations=[]))
    )
    monkeypatch.setattr(cap, "image", lambda *a: png())
    assert pilot_c.image_bytes(j, live=True) == c.composite(png(), png())


def test_observer_failures_no_retry(sandbox, monkeypatch):
    book = SimpleNamespace(snapshot=lambda: {"frozen": False})
    job = dev.jobs(dev.load())[0]
    out = sandbox / "attempt"
    out.mkdir()
    statuses = ["refused", "malformed", "ok"]
    calls = []

    def dispatch(book, req, *, output, **kw):
        index = len(calls)
        calls.append(kw)
        output.mkdir()
        if index == 2:
            (output / "response.raw").write_bytes(b"bad json")
        return dict(status=statuses[index])

    monkeypatch.setattr(pilot_c.transport, "dispatch", dispatch)
    r = pilot_c.observe(book, job, output=out, clock=None, live=False, png=png())
    assert len(calls) == 3 and r["proposals"] == [] and len(r["failures"]) == 3
    book.snapshot = lambda: {"frozen": True}
    assert (
        pilot_c.observe(book, job, output=out, clock=None, live=False, png=png())[
            "calls"
        ]
        == []
    )


def test_pin_mismatch(tmp_path, monkeypatch):
    plan = {"sha256": "a"}
    (tmp_path / "mve").mkdir()
    (tmp_path / "x").write_bytes(b"x")
    lock = {"packets": {"WO-6c": {"design_sha256": "b", "files": {}}}}
    path = tmp_path / "mve/DEPS.lock"
    path.write_text(json.dumps(lock))
    monkeypatch.setattr(pilot_c, "ROOT", tmp_path)
    with pytest.raises(Refusal, match="design_pin"):
        pilot_c.verify_pins(plan)
    packet = lock["packets"]["WO-6c"]
    packet.update(design_sha256="a", files={"x": "bad"})
    path.write_text(json.dumps(lock))
    with pytest.raises(Refusal, match="source_pin"):
        pilot_c.verify_pins(plan)
    packet["files"]["x"] = __import__("hashlib").sha256(b"x").hexdigest()
    path.write_text(json.dumps(lock))
    pilot_c.verify_pins(plan)


def test_rescore_no_reinterpretation(tmp_path, monkeypatch):
    monkeypatch.setattr(
        fp, "check", lambda *a, **kw: dict(status="checked", inferential=False)
    )
    r = rescore_c.rescore()
    assert r["total"] == 24 and r["diagnostic_rows"] == 11 and r["unavailable"] == 13
    assert r["comparative_cards"] == 0 and all(
        not row["claim_validated"] for row in r["rows"]
    )
    assert rescore_c.main(["--output", str(tmp_path / "rescore.json")]) == 0
    with pytest.raises(FileExistsError):
        rescore_c.main(["--output", str(tmp_path / "rescore.json")])
    with pytest.raises(ValueError):
        rescore_c.main(
            ["--output", str(dev.ROOT / "docs/mve/reviews/wo6b-live/new.json")]
        )


def test_accounting_tamper(tmp_path, monkeypatch):
    monkeypatch.setattr(accounting, "PIN", tmp_path / "pin.json")
    r = accounting.build()
    accounting.PIN.write_text(json.dumps(r))
    assert accounting.reconcile() == r
    accounting.PIN.write_text("{}")
    with pytest.raises(Refusal, match="reconciliation"):
        accounting.reconcile()


def test_reflection_is_joint():
    x = np.linspace(-0.9, 0.9, 1000)
    diagonal = np.column_stack((x, x))
    assert f.value(diagonal, "reflection_x", (-1, 1)) < 0.1
    assert (
        f.value(
            f.alternative(diagonal, "reflection_x", (-1, 1)), "reflection_x", (-1, 1)
        )
        > 0.99
    )


def test_spatial_pools_and_load(tmp_path, monkeypatch):
    pools = fp.sample_pools(
        "space-08",
        [len(dev.null_data("space-08", dev.STUDY_START + 60000)["values"])],
        1,
    )
    assert len(next(iter(pools.values()))) == 1

    class Empty:
        def __init__(self, seed):
            pass

        def uniform(self, n):
            return np.ones(n)

    monkeypatch.setattr(fp.native, "Mulberry", Empty)
    with pytest.raises(ValueError):
        fp.sample_pools("polar-ulam", [10], 1)
    path = tmp_path / "power.json"
    monkeypatch.setattr(fp, "OUTPUT", path)
    path.write_text(json.dumps(seal({"rows": []})))
    assert fp.load()["rows"] == []
    path.write_text(json.dumps({"rows": [], "sha256": "wrong"}))
    with pytest.raises(ValueError):
        fp.load()


def test_real_renderer_source_validation():
    # Optional local archive from the explicit read-only builder audit; no browser.
    from pathlib import Path

    stage = Path("/private/tmp/wo6c-render-source")
    if not stage.exists():
        pytest.skip("pathspec-only renderer audit archive absent")
    # check_stage expects its existing WO-1 atlas directory layout.
    hashes = {}
    for name in set(sr.PATCHES) | set(rc.PATCHES):
        raw = (stage / "vendor/zeta-explorer/dist" / name).read_text()
        hashes[name] = rc.transform(name, raw)
    assert "if(!window.__mveBlind)guides(o, d);" in hashes["prime-sphere.js"]


def test_no_prospective_source_override(monkeypatch):
    m = deepcopy(dev.inputs.manifest())
    m["snapshots"][0]["data_ref"]["path"] = "../../config/wo1b_manifest.json"
    monkeypatch.setattr(dev.inputs, "manifest", lambda: m)
    with pytest.raises(ValueError, match="eight development"):
        dev.original("spectral", "real")
    with pytest.raises(ValueError):
        fp.sample("space-08", 100, 28000000)
    with pytest.raises(ValueError):
        fp.sample_pools("unknown", [10], 1)


def test_power_cli_comparative_without_prospective_data(tmp_path, monkeypatch):
    result = {"rows": [], "seed": dev.STUDY_START}
    monkeypatch.setattr(power, "comparative_study", lambda: result)
    monkeypatch.setattr(power, "study", lambda: result)
    output = tmp_path / "power.json"
    power.main(["--comparative", "--output", str(output)])
    assert json.loads(output.read_text()) == result
    power.main(["--output", str(output)])
    with pytest.raises(SystemExit):
        power.main(["--comparative"])
    with pytest.raises(SystemExit):
        power.main(["--comparative", "--prospective", "--output", str(output)])
