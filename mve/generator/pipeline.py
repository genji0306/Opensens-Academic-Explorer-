"""Offline construction → frozen exact truth → independent rendering → v5 record."""

from dataclasses import dataclass
from mve.generator.constructions import construct
from mve.generator.render import render
from mve.generator.records import record_from
from mve.generator.truth import build_truth, FrozenTruth
from mve.record import Record


@dataclass(frozen=True)
class GeneratedDiagram:
    record: Record
    truth: FrozenTruth
    png: bytes
    render: dict


def generate(
    family,
    seed,
    *,
    style="thin",
    control=None,
    backend=None,
    budget_s=0,
    split="fit",
    code_sha="0" * 40,
):
    construction = construct(family, seed, control=control)
    truth = build_truth(
        construction["coordinates"],
        construction["premises"],
        construction["generator"],
        backend,
        budget_s=budget_s,
    )
    truth.require_fit()
    png, metadata = render(construction, style=style)
    return GeneratedDiagram(
        record_from(
            truth, png, metadata, family=family, split=split, code_sha=code_sha
        ),
        truth,
        png,
        metadata,
    )


def revise_evidence(diagram, backend, *, budget_s, at="2026-09-27T00:00:00Z"):
    """Explicit offline rerun; preserve math identity and invalidate downstream evidence."""
    from mve.record import transition

    data = diagram.truth.data()
    generator = {
        k: data["generator"][k] for k in ("id", "version", "config_sha256", "seed")
    }
    truth = build_truth(
        data["math_coordinates"],
        data["premises"],
        generator,
        backend,
        budget_s=budget_s,
    )
    truth.require_fit()
    record = transition(
        diagram.record,
        "edit",
        actor="human:offline-evidence-rerun",
        expected_revision=diagram.record.to_dict()["revision"],
        at=at,
        payload={
            "patch": [
                {"op": "replace", "path": "/sources/0/sha256", "value": truth.sha256},
                {
                    "op": "replace",
                    "path": "/sources/0/generator",
                    "value": truth.data()["generator"],
                },
            ]
        },
    )
    return GeneratedDiagram(record, truth, diagram.png, diagram.render)
