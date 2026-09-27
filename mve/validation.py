"""Semantic checks that JSON Schema cannot express."""

import math
import re
from datetime import datetime
from mve.errors import RecordError
from mve.graph import reject_hypothesis_support
from mve.exact import canonical_exact
from mve.predicates import REGISTRY, canonical_proposition


def require(condition, message):
    if not condition:
        raise RecordError(message)


def active(node):
    return node.get("valid", True)


def proposition(prop, data, allowed_binders=False, formal=False):
    value_exact = prop.get("value_exact")
    if value_exact is not None:
        try:
            canonical = canonical_exact(value_exact)
        except ValueError as exc:
            raise RecordError(f"invalid exact expression: {exc}") from exc
        require(canonical == value_exact, "noncanonical exact expression")
    binders = {b["name"]: b for b in data["problem"]["binders"]}
    entities = {e["id"]: e for e in data["entities"]}
    require(canonical_proposition(prop) == prop, "noncanonical proposition")
    row = REGISTRY[prop["pred"]]
    for arg, kind in zip(prop["args"], row["argument_kinds"]):
        if allowed_binders and arg in binders:
            require(
                binders[arg]["type"].lower() == kind, "binder argument kind mismatch"
            )
        else:
            require(arg in entities, "unknown proposition entity")
            require(entities[arg]["kind"] == kind, "entity argument kind mismatch")
    if prop.get("value") is not None:
        require(math.isfinite(prop["value"]), "nonfinite proposition value")


def check_problem(data, graph):
    problem = data["problem"]
    names = [b["name"] for b in problem["binders"]]
    require(len(set(names)) == len(names), "duplicate binder name")
    links = [b["entity"] for b in problem["binders"] if b.get("entity")]
    require(len(set(links)) == len(links), "ambiguous binder entity mapping")
    for b in problem["binders"]:
        if b.get("entity"):
            require(
                b["entity"] in graph
                and graph[b["entity"]].get("kind") == b["type"].lower(),
                "binder entity is missing or has wrong kind",
            )
    groups = problem["premises"] + problem["nondegeneracy"]
    if problem["goal"]:
        groups += [problem["goal"]]
    for item in groups:
        if not active(item):
            continue
        reject_hypothesis_support(item["depends_on"], graph)
        proposition(item["proposition"], data, allowed_binders=True, formal=True)
        deps = item["depends_on"]
        require(
            len(deps) == 1 and graph[deps[0]].get("kind") in ("text", "truth_artifact"),
            "problem proposition needs exactly one addressable source",
        )
    for item in problem["nondegeneracy"]:
        require(
            item["proposition"]["pred"] in ("Distinct", "NotCollinear"),
            "invalid nondegeneracy predicate",
        )
    return groups


def check_sources(data):
    for source in data["sources"]:
        require(not source["depends_on"], "sources cannot depend on computed evidence")
        prefix = "txt_" if source["kind"] == "text" else "geo_"
        require(source["id"].startswith(prefix), "source id kind mismatch")
        if source["kind"] == "text":
            span = source.get("span")
            require(
                span is not None and span[0] <= span[1],
                "text source needs ordered span",
            )
    truth = data["image"].get("truth")
    if truth:
        sources = {s["id"]: s for s in data["sources"]}
        source = sources.get(truth["source"], {})
        require(
            source.get("kind") == "truth_artifact",
            "truth source must resolve to truth artifact",
        )
        require(
            source.get("generator", {}).get("coordinates_exact") is True,
            "truth-scored data require exact algebraic coordinates",
        )
        require(
            data["image"].get("ground_truth_ref") == truth["source"],
            "truth source mismatch",
        )
    elif data["image"].get("ground_truth_ref") is not None:
        raise RecordError("ground truth reference requires truth metadata")


def check_entities(data, graph, groups):
    binding = {b["name"]: b.get("entity") for b in data["problem"]["binders"]}
    for ent in data["entities"]:
        if not active(ent):
            continue
        required = {
            p["id"]
            for p in groups
            if ent["id"] in [binding.get(a, a) for a in p["proposition"]["args"]]
        }
        require(
            required <= set(ent["depends_on"]), "missing entity-to-problem dependency"
        )
        require(set(ent.get("on", [])) <= set(graph), "dangling incidence reference")
        require(
            all(x.startswith("ent_") for x in ent.get("on", [])),
            "incidence must name entities",
        )
        for geo in ent["geometries"]:
            check_geometry(ent, geo, data, graph)


GEOMETRY_LENGTHS = {
    "point": 2,
    "crossing": 2,
    "segment": 4,
    "line": 4,
    "ray": 4,
    "circle": 3,
    "arc": 5,
    "tick": 4,
    "arrow": 4,
    "angle_mark": 4,
    "right_angle_mark": 4,
}


def check_geometry(ent, geo, data, graph):
    p = geo["params"]
    kind = ent["kind"]
    require(
        (len(p) == GEOMETRY_LENGTHS[kind])
        if kind in GEOMETRY_LENGTHS
        else (len(p) >= 6 and len(p) % 2 == 0),
        "geometry parameter count mismatch",
    )
    require(all(math.isfinite(x) for x in p), "nonfinite geometry")
    require(ent["id"] in geo["depends_on"], "geometry must depend on its owner entity")
    coordinates = (
        p[:2]
        if kind in ("circle", "arc", "tick", "arrow", "angle_mark", "right_angle_mark")
        else p
    )
    require(
        all(0 <= x <= data["image"]["width"] for x in coordinates[::2]),
        "x coordinate out of frame",
    )
    require(
        all(0 <= y <= data["image"]["height"] for y in coordinates[1::2]),
        "y coordinate out of frame",
    )
    if kind in ("circle", "arc"):
        require(p[2] > 0, "radius must be positive")
    if kind in ("tick", "arrow", "angle_mark", "right_angle_mark"):
        require(p[2] > 0 and p[3] > 0, "mark dimensions must be positive")
    if geo["source"] == "image_measurement":
        require(
            geo.get("localization_sigma_px") is not None,
            "image geometry needs localization uncertainty",
        )
    if geo["source"] == "ground_truth":
        require(
            any(graph[x].get("kind") == "truth_artifact" for x in geo["depends_on"]),
            "ground truth geometry needs truth source",
        )
    if geo.get("pieces") is not None:
        require(kind == "strand", "pieces belong only to strands")
        for piece in geo["pieces"]:
            require(
                len(piece) >= 4
                and len(piece) % 2 == 0
                and all(math.isfinite(x) for x in piece),
                "invalid strand piece",
            )


def check_observations(data, graph):
    for obs in data["observations"]:
        if not active(obs):
            continue
        require(
            obs["call"] <= data["provenance"]["perceiver_calls"],
            "unrecorded perception call",
        )
        deps = [graph[x] for x in obs["depends_on"]]
        require(
            all(d.get("source") == f'perceiver_call_{obs["call"]}' for d in deps),
            "observation must depend on its own call geometries",
        )
        if "proposition" in obs:
            proposition(obs["proposition"], data)
            owners = {x for d in deps for x in d["depends_on"] if x.startswith("ent_")}
            require(
                set(obs["proposition"]["args"]) <= owners,
                "missing observation geometry dependencies",
            )


def check_measurements(data, graph):
    for mea in data["measurements"]:
        if not active(mea):
            continue
        proposition(mea["proposition"], data)
        deps = [graph[x] for x in mea["depends_on"]]
        geos = [g for g in deps if "params" in g]
        require(geos, "measurement needs exact geometry inputs")
        owners = {x for g in geos for x in g["depends_on"] if x.startswith("ent_")}
        require(
            set(mea["proposition"]["args"]) <= owners,
            "measurement missing argument geometry",
        )
        require(
            all("params" in g or g["id"].startswith("obs_") for g in deps),
            "invalid measurement dependency kind",
        )
        if mea["method"] == "image_measurement":
            require(
                all(g["source"] == "image_measurement" for g in geos),
                "image measurement uses predicted coordinates",
            )
        for name in ("residual", "tolerance", "uncertainty"):
            if mea.get(name) is not None:
                require(
                    mea[name] >= 0 and math.isfinite(mea[name]),
                    "invalid measurement magnitude",
                )
        if mea["outcome"] in ("consistent", "inconsistent"):
            consistent = mea["residual"] <= mea["tolerance"]
            require(
                consistent == (mea["outcome"] == "consistent"),
                "measurement outcome contradicts residual",
            )


def check_adoptions(data, graph):
    for asm in data["assumptions"]:
        if not active(asm):
            continue
        reject_hypothesis_support(asm["depends_on"], graph)
        proposition(asm["proposition"], data, formal=True)
        deps = [graph[x] for x in asm["depends_on"]]
        if asm["adopted_by"].startswith("human:"):
            adopted = [
                j
                for j in deps
                if j.get("verdict") == "adopt" and j.get("judge") == asm["adopted_by"]
            ]
            require(len(adopted) == 1, "human assumption needs own adopt judgment")
            target = graph[adopted[0]["target"]]
            require(
                equivalent(
                    asm["proposition"],
                    target.get("proposition", target.get("target")),
                    data,
                ),
                "adopted assumption differs from its target",
            )
        elif asm["adopted_by"] == "text":
            require(
                all(j.get("kind") == "text" for j in deps),
                "text adoption needs text source",
            )
        else:
            require(
                all(not j["id"].startswith(("asm_", "prop_", "der_")) for j in deps),
                "policy assumption must cite original evidence",
            )


def equivalent(left, right, data):
    if not isinstance(right, dict):
        return False
    mapping = {
        b["name"]: b["entity"] for b in data["problem"]["binders"] if b.get("entity")
    }
    return canonical_proposition(left, mapping) == canonical_proposition(right, mapping)


def check_judgments(data, graph):
    from mve.verdicts.catalogue import check_label

    for jud in data["judgments"]:
        if not active(jud):
            continue
        timestamp(jud["at"])
        check_label(jud, graph)
        if jud["judge"].startswith("model:"):
            require(jud["weight"] == 0.5, "model judgment weight must be one half")
        if jud["question"] == "review":
            require(
                jud["judge"].startswith("human:")
                or jud["judge"] in ("audit:Opus", "audit:Sol"),
                "ineligible reviewer",
            )
        require(
            jud["target"] in graph and jud["target"] in jud["depends_on"],
            "judgment must depend on target",
        )
        if jud["verdict"] in ("adopt", "decline"):
            require(
                jud["judge"].startswith("human:"), "only a human can adopt or decline"
            )
        if jud["judge"].startswith("human:"):
            require(jud["weight"] == 1, "human judgment weight must be one")


def check_derivations(data, graph):
    for der in data["derivations"]:
        if not active(der):
            continue
        reject_hypothesis_support(der["depends_on"], graph)
        proposition(der["target"], data, formal=True)
        require(
            der["depends_on"]
            and all(x.startswith(("prm_", "ndg_", "asm_")) for x in der["depends_on"]),
            "derivation needs explicit premises; measurement is not a premise",
        )
        if der["outcome"] == "counterexample":
            w = der["witness"]
            require(
                w.get("exact") is True
                or (w.get("tolerance") is not None and w["tolerance"] >= 0),
                "numeric counterexample requires tolerance",
            )


def check_decisions(data):
    for dec in data["decisions"]:
        if not active(dec):
            continue
        low, high = dec["threshold_low"], dec["threshold_high"]
        require(low <= high, "reversed decision thresholds")
        probs = dec.get("probabilities")
        if probs:
            require(
                abs(sum(probs.values()) - 1) < 1e-8,
                "probabilities must sum to one including abstention",
            )
        if not dec["depends_on"]:
            require(
                dec["route"] in ("human", "disabled"),
                "missing decision evidence must route human",
            )
        if dec["route"] == "disabled":
            continue
        if dec["abstained"] or dec["input_tokens"] > 512:
            require(
                dec["abstained"] and dec["route"] == "human",
                "overflow or abstention must route human",
            )
        else:
            expected = (
                "act"
                if dec["confidence"] > high
                else ("llm" if dec["confidence"] > low else "human")
            )
            require(dec["route"] == expected, "incorrect boundary routing")


def check_candidates(data, graph):
    for candidate in data.get("candidates", []):
        if not active(candidate):
            continue
        timestamp(candidate["at"])
        proposition(candidate["proposition"], data)
        require(
            set(candidate["proposition"]["args"]) <= set(candidate["depends_on"]),
            "candidate must depend on its proposition entities",
        )


def timestamp(value):
    require(
        isinstance(value, str)
        and re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])",
            value,
        ),
        "timestamp must be an RFC 3339 date-time with timezone",
    )
    try:
        datetime.fromisoformat(value)
    except ValueError as exc:
        raise RecordError("invalid timestamp") from exc
