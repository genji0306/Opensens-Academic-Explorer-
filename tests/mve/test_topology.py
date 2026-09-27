"""WP-10 tests written before implementation; exact fixtures, never image inference."""

from dataclasses import replace
from fractions import Fraction as F
import json

import pytest

from mve.topology.model import Diagram, TopologyError, canonical_pd
from mve.topology.geometry import Skeleton, decode, intersections
from mve.topology.generator import fixture, corpus, frozen_split, write_corpus
from mve.topology.scoring import score
from mve.topology.checks import snappy_checks, certificate


@pytest.mark.parametrize(
    "family,c,components",
    [
        ("unknot", 0, 1),
        ("trefoil", 3, 1),
        ("figure_eight", 4, 1),
        ("hopf", 2, 2),
        ("unlink", 0, 2),
    ],
)
def test_exact_geometry_and_truth(family, c, components):
    item = fixture(family)
    actual = decode(item.skeleton)
    assert actual == item.truth
    assert len(actual.pd) == c
    assert len(actual.components) == components
    assert actual.mirror is False
    assert len(intersections(item.skeleton)) == c


@pytest.mark.parametrize(
    "family", ["unknot", "trefoil", "figure_eight", "hopf", "unlink"]
)
@pytest.mark.parametrize(
    "variant", ["base", "mirror", "r1", "r1_negative", "r2", "near_miss"]
)
def test_variants_and_gaps(family, variant):
    item = fixture(family, variant)
    assert decode(item.skeleton) == item.truth
    assert len(item.truth.pd) <= 7
    assert len(item.truth.components) == len(fixture(family).truth.components)
    assert len(item.skeleton.gaps) == len(item.truth.pd)
    assert item.truth.mirror == (variant == "mirror")
    assert item.family == family


def test_missing_gap_is_ambiguous_not_guessed():
    item = fixture("trefoil")
    with pytest.raises(TopologyError, match="ambiguous_source"):
        decode(replace(item.skeleton, gaps=()))
    with pytest.raises(TopologyError):
        decode(replace(item.skeleton, gaps=item.skeleton.gaps * 2))


def test_singular_crossings_rejected():
    # Non-adjacent vertex touch, overlap and triple intersection.
    for points in [
        (((0, 0), (2, 0), (1, 1), (1, 0), (0, 1)),),
        (((0, 0), (3, 0), (3, 2), (1, 0), (2, 0), (0, 2)),),
        (
            (
                (-3, -1),
                (3, 1),
                (4, 4),
                (-3, 1),
                (3, -1),
                (4, -4),
                (0, -3),
                (0, 3),
                (-4, 4),
            ),
        ),
    ]:
        with pytest.raises(TopologyError):
            intersections(Skeleton(points, (), False))


def test_pd_validation_and_limits():
    d = fixture("trefoil").truth
    with pytest.raises(TopologyError):
        Diagram(((1, 2, 3, 4),), ((1, 2, 3, 4),), (1,), False)
    with pytest.raises(TopologyError):
        replace(d, signs=(0,) * 3)
    with pytest.raises(TopologyError):
        replace(d, components=((1, 2),))
    with pytest.raises(TopologyError):
        replace(d, mirror="yes")
    assert Diagram((), ((1,),), (), False).pd == ()


def test_canonical_only_declared_equivalences():
    d = fixture("trefoil").truth
    cycle = d.components[0]
    mapping = dict(zip(cycle, cycle[1:] + cycle[:1]))
    shifted = replace(d, pd=tuple(tuple(mapping[a] for a in x) for x in d.pd))
    assert d.pd != shifted.pd
    assert canonical_pd(d) == canonical_pd(shifted)
    assert canonical_pd(d) != canonical_pd(fixture("trefoil", "mirror").truth)
    assert canonical_pd(d) != canonical_pd(fixture("trefoil", "r1").truth)
    assert canonical_pd(d) != canonical_pd(fixture("trefoil", "r2").truth)
    link = fixture("hopf").truth
    assert canonical_pd(link) == canonical_pd(
        replace(link, components=link.components[::-1])
    )


def test_scores_missing_malformed_nulls_and_denominators():
    items = [fixture("trefoil"), fixture("hopf"), fixture("unknot")]
    result = score(
        items,
        {items[0].id: items[0].truth, items[1].id: {"bad": True}},
        knot_types={items[0].id: items[0].knot_type},
    )
    assert result["exact"]["numerator"] == 1
    assert result["exact"]["denominator"] == 3
    assert result["unknowns"] == 2
    assert result["orientation"]["micro"]["denominator"] == 5
    assert result["orientation"]["micro"]["numerator"] == 3
    assert result["orientation"]["macro"]["denominator"] == 2
    assert result["nulls"]["orientation_complete"]["mean"] == pytest.approx(
        float((F(1, 8) + F(1, 4) + 1) / 3)
    )
    assert result["nulls"]["knot_type"]["uniform"] == 1 / 3
    assert result["nulls"]["knot_type"]["majority"] == 1 / 3
    assert result["invariant_consistency"]["denominator"] == 0
    assert result["component_validity"]["denominator"] == 3


def test_corpus_png_and_family_freeze(tmp_path):
    items = corpus()
    split = frozen_split(items)
    assert len(items) == 30
    families = {}
    for row in split.manifest()["items"]:
        assert families.setdefault(row["family"], row["split"]) == row["split"]
    result = write_corpus(tmp_path)
    assert result["scope"] == "synthetic_coordinate_self_consistency"
    assert result["g5_status"] == "not established"
    assert result["scores"]["exact"]["numerator"] == 30
    assert len(list(tmp_path.glob("images/*.png"))) == 30
    assert (
        (tmp_path / "images/trefoil-base.png")
        .read_bytes()
        .startswith(b"\x89PNG\r\n\x1a\n")
    )
    before = (tmp_path / "receipt.json").read_bytes()
    write_corpus(tmp_path)
    assert (tmp_path / "receipt.json").read_bytes() == before
    assert json.loads((tmp_path / "split.json").read_text())["retired"] is True


def test_optional_checks_and_certificate():
    d = fixture("trefoil").truth
    checks = snappy_checks(d)
    assert checks["construction"]["operation"] == "snappy.Link(pd)"
    assert checks["identification"]["operation"] == "Link.exterior().identify()"
    assert checks["invariant"]["operation"] == "Link.jones_polynomial()"
    assert checks["construction"]["status"] == "unavailable"
    lean = certificate(d)
    assert "by decide" in lean and "successor" in lean
    assert "sorry" not in lean and "axiom" not in lean
    with pytest.raises(TopologyError):
        certificate(fixture("hopf").truth)


def test_hand_numbered_pd_and_sign_convention():
    # Arc 1 enters the lowest crossing on its underpass; slots then run CCW.
    assert fixture("trefoil").truth.pd == ((1, 4, 2, 5), (3, 6, 4, 1), (5, 2, 6, 3))
    assert fixture("trefoil").truth.signs == (-1, -1, -1)
    assert fixture("trefoil", "mirror").truth.signs == (1, 1, 1)
    assert fixture("figure_eight").truth.pd == (
        (1, 7, 2, 6),
        (3, 8, 4, 1),
        (5, 3, 6, 2),
        (7, 4, 8, 5),
    )
    assert fixture("hopf").truth.pd == ((1, 3, 2, 4), (4, 2, 3, 1))
    assert fixture("unknot", "r1_negative").truth.signs == (1,)


def test_reporting_never_promotes_self_consistency(tmp_path):
    from mve.reporting.topology import topology_evidence

    receipt = write_corpus(tmp_path)
    table, checks = topology_evidence(receipt)
    from mve.reporting.gates import evaluate_gate

    assert evaluate_gate("G5", checks)["status"] == "not established"
    assert checks["synthetic"]["outcome"] is None
    assert table["scores"]["exact"]["numerator"] == 30
    for change in (
        {"perception_runs": 1},
        {"g5_status": "established"},
        {"scope": "perception"},
        {"external_diagrams": 1},
    ):
        with pytest.raises(ValueError):
            topology_evidence({**receipt, **change})
    assert topology_evidence(None)[0]["scores"] is None


def test_lean_certificate_kernel_and_negative_control(monkeypatch):
    from mve.topology.checks import check_certificate

    source = certificate(fixture("trefoil").truth)
    receipt = check_certificate(fixture("trefoil").truth)
    assert receipt["status"] == "kernel_checked", receipt
    assert receipt["scope"] == "decoded_record_only"
    assert receipt["axioms"] == []
    bad = source.replace("walk 6 1 = 1", "walk 6 1 = 2")
    assert bad != source
    monkeypatch.setattr("mve.topology.checks.certificate", lambda diagram: bad)
    assert check_certificate(fixture("trefoil").truth)["status"] == "error"


def test_pd_canonicalization_is_not_knot_equivalence_or_row_sort():
    d = fixture("trefoil").truth
    reverse = replace(d, pd=(d.pd[0], d.pd[2], d.pd[1]))
    assert canonical_pd(d) != canonical_pd(reverse)
    item = fixture("trefoil")
    result = score([item], {item.id: fixture("trefoil", "r2").truth})
    assert result["exact"]["value"] == 0
    assert result["canonicalized"]["value"] == 0
    assert result["orientation"]["micro"]["value"] == 0
    assert result["errors"]["crossing_detection"] == 1


@pytest.mark.parametrize(
    "kwargs",
    [
        {"pd": ((1, 2, 3),), "signs": (1,)},
        {"components": ()},
        {"pd": ((1, 2, 2, 1),) * 8, "signs": (-1,) * 8},
        {"components": ((),)},
        {"components": ((True,),)},
        {"components": ((2,),)},
        {"pd": (), "components": ((1, 2),), "signs": ()},
        {"pd": ((1, 2, 2, 1),), "components": ((1, 2),), "signs": (1,)},
        {"pd": ((1, 2, 2, 1),), "components": ((1,), (2,)), "signs": (-1,)},
    ],
)
def test_invalid_pd_contract(kwargs):
    with pytest.raises(TopologyError):
        Diagram(**{"pd": (), "components": ((1,),), "signs": (), **kwargs})


def test_invalid_error_category():
    with pytest.raises(ValueError, match="unknown"):
        TopologyError("other", "bad")


@pytest.mark.parametrize(
    "components",
    [
        (),
        (((0, 0), (1.0, 0), (0, 1)),),
        (((0, 0), (0, 1), (1, 0)),),
        (((0, 0), (1, 0), (1, 0), (1, 1), (0, 1)),),
        (((0, 0), (2, 0), (1, 0), (2, 2), (0, 2)),),
    ],
)
def test_invalid_exact_skeleton(components):
    with pytest.raises(TopologyError):
        intersections(Skeleton(components, (), False))


def test_collinear_overlap_nonadjacent_and_excess_crossings():
    from mve.topology.geometry import meet
    from mve.topology.generator import braid

    with pytest.raises(TopologyError, match="overlap"):
        meet((0, 0), (3, 0), (1, 0), (2, 0))
    components, _ = braid(2, (1,) * 8)
    with pytest.raises(TopologyError, match="seven crossings"):
        intersections(Skeleton(components, (), False))


def test_gap_may_not_hide_two_crossings_or_float_free():
    from mve.topology.geometry import Gap

    item = fixture("trefoil")
    extra = Gap(0, 0, F(1, 4), F(3, 4))
    with pytest.raises(TopologyError):
        decode(replace(item.skeleton, gaps=(*item.skeleton.gaps, extra)))


def test_generator_rejects_unknown_recipe_and_missing_symbolic_edge():
    from mve.topology.generator import locate

    with pytest.raises(ValueError):
        fixture("absent")
    with pytest.raises(ValueError):
        fixture("unknot", "bad")
    with pytest.raises(ValueError):
        locate((((0, 0), (1, 0), (0, 1)),), ((2, 2), (3, 3)))


def test_score_controls_and_empty_denominators():
    item = fixture("trefoil")
    with pytest.raises(ValueError):
        score([item, item], {})
    with pytest.raises(ValueError):
        score([item], {"absent": item.truth})
    with pytest.raises(ValueError):
        score([item], {}, knot_types={"absent": "unknot"})
    empty = score([], {})
    assert empty["macro"]["value"] is None
    assert empty["nulls"]["knot_type"]["uniform"] is None
    mirrored = score([item], {item.id: fixture("trefoil", "mirror").truth})
    assert mirrored["exact"]["value"] == 0
    # Fixed arc correspondence with every crossing switched gives opposite signs.
    d = item.truth
    switched = replace(
        d, pd=tuple((r[1], r[2], r[3], r[0]) for r in d.pd), signs=(1,) * 3
    )
    result = score([item], {item.id: switched})
    assert result["errors"] == {"orientation": 1}
    assert result["orientation"]["micro"]["value"] == 0
    assert result["orientation"]["unaligned_diagrams"] == 0
    shifted = replace(d, pd=tuple(tuple(a % 6 + 1 for a in r) for r in d.pd))
    assert score([item], {item.id: shifted})["canonicalized"]["value"] == 1
    un = fixture("unknot")
    result = score([un], {un.id: fixture("unlink").truth})
    assert result["exact"]["value"] == 1  # Precisely identical PD lists, both empty.
    assert result["complete"]["value"] == 0
    assert result["component_validity"]["value"] == 0


def test_topology_reporting_count_corruption_and_markdown(tmp_path):
    from copy import deepcopy
    from mve.reporting.topology import topology_evidence, topology_markdown

    receipt = write_corpus(tmp_path)
    evidence, _ = topology_evidence(receipt)
    assert "not G5" in "\n".join(topology_markdown({"topology": evidence}))
    assert "No committed" in "\n".join(topology_markdown({}))
    changed = deepcopy(receipt)
    changed["scores"]["exact"]["numerator"] = 29
    with pytest.raises(ValueError, match="aggregate"):
        topology_evidence(changed)
    changed = deepcopy(receipt)
    changed["scores"]["rows"][0]["crossings"] = 8
    with pytest.raises(ValueError, match="crossing count"):
        topology_evidence(changed)


def test_cli(tmp_path, monkeypatch):
    from mve.topology.__main__ import main

    monkeypatch.setattr("sys.argv", ["topology", "--output", str(tmp_path)])
    main()
    import runpy
    from pathlib import Path

    runpy.run_path(str(Path("mve/topology/__main__.py").resolve()), run_name="__main__")
    assert (tmp_path / "receipt.json").exists()


def test_certificate_unavailable_timeout(monkeypatch):
    import subprocess
    from pathlib import Path
    from mve.topology.checks import check_certificate

    d = fixture("unknot").truth
    with monkeypatch.context() as m:
        m.setattr(Path, "is_file", lambda self: False)
        assert check_certificate(d)["status"] == "unavailable"

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("lean", 30)

    monkeypatch.setattr(subprocess, "run", timeout)
    assert check_certificate(d)["status"] == "timeout"


def test_decoder_error_category_survives_scoring():
    item = fixture("trefoil")
    error = TopologyError("ambiguous_source", "missing gap")
    assert score([item], {item.id: error})["errors"] == {"ambiguous_source": 1}


def test_orphan_gap_on_crossing_free_circle():
    from mve.topology.geometry import Gap

    s = fixture("unknot").skeleton
    with pytest.raises(TopologyError, match="unassociated"):
        decode(replace(s, gaps=(Gap(0, 0, F(1, 4), F(3, 4)),)))


def test_reporting_integration_with_topology_receipt(monkeypatch):
    from pathlib import Path
    from mve.reporting.sources import Evidence
    from mve.reporting.topology import TOPOLOGY, GRAMMAR_DOC
    from mve.reporting.current import build_report
    from mve.reporting.render import markdown, serialize
    from hashlib import sha256

    original = Evidence.read

    def read(self, path):
        if path in (TOPOLOGY, GRAMMAR_DOC):
            data = Path(path).read_bytes()
            self.sources[path] = {"sha256": sha256(data).hexdigest()}
            return data
        return original(self, path)

    original_optional = Evidence.optional

    def optional(self, path):
        return self.json(path) if path == TOPOLOGY else original_optional(self, path)

    monkeypatch.setattr(Evidence, "read", read)
    monkeypatch.setattr(Evidence, "optional", optional)
    report = build_report(Path("."), "1e6db728bd0")
    assert report["gates"]["G5"]["status"] == "not established"
    assert report["gates"]["G5"]["counts"] == {
        "criteria_expected": 4,
        "criteria_evidenced": 1,
        "criteria_met": 1,
    }
    assert report["topology"]["scores"]["exact"]["numerator"] == 30
    assert markdown(report) == markdown(json.loads(serialize(report)))
    assert "not G5" in markdown(report)
