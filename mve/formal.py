"""Evidence authorization is not a substitute for an independent Lean receipt."""

from mve.graph import reject_hypothesis_support
from mve.validation import require, active, proposition, equivalent

AXIOMS = {"propext", "Classical.choice", "Quot.sound"}


def check_formal(data, graph):
    formal = data["formal"]
    reject_hypothesis_support(formal["depends_on"], graph)
    for prop in formal["propositions"]:
        check_authorization(prop, data, graph)
    props = {p["id"] for p in formal["propositions"] if active(p)}
    require(set(formal["depends_on"]) <= set(graph), "dangling formal dependency")
    for key in ("typecheck", "proof", "equivalence", "render_back"):
        node = formal.get(key)
        if not node or not active(node):
            continue
        required = props if key == "typecheck" else {"tc_1"}
        require(
            required <= set(node["depends_on"]), "missing formal artifact dependency"
        )
    check_status(data, props)
    if formal["status"] == "proved":
        check_proof(formal["proof"])


def check_authorization(prop, data, graph):
    if not active(prop):
        return
    reject_hypothesis_support(prop["depends_on"], graph)
    proposition(prop["proposition"], data, formal=True)
    require(
        len(prop["depends_on"]) == 1,
        "formal proposition needs exactly one authorizing node",
    )
    ref = graph[prop["depends_on"][0]]
    support = prop["support"]
    if prop["role"] == "nondegeneracy":
        require(
            prop["proposition"]["pred"] in ("Distinct", "NotCollinear"),
            "invalid formal nondegeneracy",
        )
    if prop["role"] == "goal":
        require(support == "goal_source", "goal cannot masquerade as proved hypothesis")
    else:
        require(support != "goal_source", "goal cannot authorize hypothesis")
    prefixes = {
        "problem_text": ("prm_", "ndg_"),
        "assumption": ("asm_",),
        "derived": ("der_",),
        "goal_source": ("goal_",),
    }
    require(ref["id"].startswith(prefixes[support]), "unauthorized evidence class")
    if support == "derived":
        require(ref["outcome"] == "proved", "unknown derivation cannot authorize")
    require(
        equivalent(
            prop["proposition"], ref.get("proposition", ref.get("target")), data
        ),
        "authorizing proposition is not equal",
    )


def check_status(data, props):
    formal = data["formal"]
    status = formal["status"]
    if status in (
        "emitted",
        "typechecked",
        "proof_attempted",
        "proved",
        "counterexample",
    ):
        require(
            formal.get("ir_sha256")
            and formal.get("statement_sha256")
            and data["versions"].get("lean_lock_sha"),
            "formalized record needs statement, IR and Lean lock hashes",
        )
        require(props, "formal artifact needs current propositions")
        goals = [p for p in formal["propositions"] if active(p) and p["role"] == "goal"]
        require(
            len(goals)
            == (
                1 if data["problem"]["goal"] and active(data["problem"]["goal"]) else 0
            ),
            "formal goal missing or invented",
        )
    if status in ("typechecked", "proof_attempted", "proved", "counterexample"):
        require(
            formal.get("typecheck")
            and active(formal["typecheck"])
            and formal["typecheck"]["ok"],
            "successful current typecheck required",
        )


def check_proof(proof):
    require(
        active(proof)
        and proof["axiom_policy"] == "mathlib_standard_only"
        and set(proof["axioms"]) <= AXIOMS,
        "proof violates axiom policy",
    )
    require(
        all(
            proof[k]
            for k in (
                "ok",
                "sorry_free",
                "dependency_closure_checked",
                "statement_matches_accepted",
            )
        ),
        "proof receipt incomplete",
    )
