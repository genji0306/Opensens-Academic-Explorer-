"""Evidence strength is explicit; correspondence is not a semantic-rubric pass."""

from mve.formalizer.emitter import emit
from mve.identity import digest
from hashlib import sha256

LEVELS = ("kernel_checked", "machine_supported", "reviewer_judged", "unresolved")


def binder_mapping(ir):
    return [dict(b, lean=f"p{i}") for i, b in enumerate(ir["binders"])]


def proposition_hash(ir):
    return digest(
        {k: ir[k] for k in ("binders", "premises", "goal", "exact_constants")}
    )


def assess(reference, candidate, source, *, claimed_level=None, review=None):
    if claimed_level is not None:
        raise ValueError("evidence levels are computed; kernel checker is unavailable")
    identity = {
        "reference_ir_sha256": digest(reference),
        "candidate_ir_sha256": digest(candidate),
        "statement_sha256": sha256(source.encode()).hexdigest(),
    }
    same = digest(reference) == digest(candidate)
    machine = same and source in (emit(reference), emit(reference) + "\n")
    result = {
        **identity,
        "level": "machine_supported" if machine else "unresolved",
        "basis": "exact IR, binder mapping and deterministic emission"
        if machine
        else "not established",
        "semantic_acceptance": False,
        "proof_checked": False,
    }
    if review is not None:
        validate_review(review, identity)
        result["review"] = review
        result["semantic_acceptance"] = all(review["rubric"].values())
        if not machine:
            result.update(level="reviewer_judged", basis="blinded component rubric")
    return result


def validate_review(review, identity):
    if any(review.get(k) != v for k, v in identity.items()):
        raise ValueError("review does not bind these artifacts")
    if (
        not isinstance(review.get("reviewer"), str)
        or not review["reviewer"].strip()
        or not isinstance(review.get("rationale"), str)
        or not review["rationale"].strip()
        or review.get("blinded") is not True
    ):
        raise ValueError("blinded reviewer identity and rationale required")
    rubric = review.get("rubric", {})
    if set(rubric) != {"binders", "premises", "goal", "nondegeneracy"} or any(
        type(v) is not bool for v in rubric.values()
    ):
        raise ValueError("complete boolean component rubric required")
