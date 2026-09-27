"""Only record-bound examples from the retrieval partition; no arbitrary source strings."""

from dataclasses import dataclass
from mve.formalizer.ir import build_ir
from mve.evaluation.splits import SplitError
from mve.formalizer.repairs import Candidate
from mve.formalizer.emitter import emit


@dataclass(frozen=True)
class Example:
    image_sha256: str
    family: str
    split_sha256: str
    candidate: Candidate

    def ir(self):
        return self.candidate.ir()


def examples(records, split):
    split.require_evaluation()
    items = {r["id"]: r for r in split.manifest()["items"]}
    result, seen = [], set()
    for record in records:
        data = record.to_dict()
        image = data["image"]["sha256"]
        if image in seen:
            raise SplitError("duplicate example image")
        seen.add(image)
        if image not in items:
            raise SplitError("example image missing from frozen split")
        item = items[image]
        truth = data["image"].get("truth")
        if truth and (truth["family"], truth["split"]) != (
            item["family"],
            item["split"],
        ):
            raise SplitError("example origin conflicts with frozen split")
        if item["split"] != "retrieval":
            raise SplitError("examples must belong to retrieval families")
        ir = build_ir(record)
        result.append(
            Example(image, item["family"], split.sha256, Candidate.make(ir, emit(ir)))
        )
    return tuple(result)


def nearest(ir, catalog):
    def predicates(value):
        return {
            n["proposition"]["pred"] for n in [*value["premises"], value["goal"]] if n
        }

    query = predicates(ir)
    return min(
        catalog,
        key=lambda e: (-len(query & predicates(e.ir())), e.image_sha256),
        default=None,
    )
