"""Small synthetic WO-1 manifests; never evidence for GO gates."""

from copy import deepcopy
import json
from mve.observer import snapshots as s
from mve.observer.card import card_hash
from tests.mve.observer.test_runner import small_card
from tests.mve.perceiver_helpers import ROOT, reply, mutate_reply
from mve.perceiver import Replay


def fixture(root, k=1, views=1):
    root.mkdir(parents=True, exist_ok=True)
    entries, strata = [], []
    for module in ("spectral", "field-dyson")[: min(k, 2)]:
        st = dict(
            id=module + " × zero spacings",
            module=module,
            family="zero spacings",
            discovery=[],
            replication=[],
            donors=[],
            contrast_discovery=[],
            contrast_replication=[],
        )
        for cluster in range(k if k == 1 else (k + (module == "spectral")) // 2):
            for role, key in [
                ("discovery", "discovery"),
                ("replication", "replication"),
                ("donor", "donors"),
            ]:
                block = f"{module}-{cluster}-{role}"
                st[key].append(block)
                for view in range(views):
                    for null in (False, True):
                        ident = f"{block}-{view}-{int(null)}"
                        twin = f"{block}-{view}-{int(not null)}"
                        data = root / f"{block}-{int(null)}.json"
                        data.write_text(
                            json.dumps(
                                dict(
                                    values=[0.5, 1, 1.5],
                                    height=1e12,
                                    identity=block + str(null),
                                )
                            )
                        )
                        png = root / (ident + ".png")
                        png.write_bytes(
                            (ROOT / "public/development_0.png").read_bytes()
                        )
                        clean = s.blind_png(png.read_bytes(), (0, 0, 288, 288), [])
                        png.write_bytes(clean)
                        seed = (
                            len(strata) * 1000
                            + cluster * 10
                            + ["discovery", "replication", "donor"].index(role)
                        )
                        job = dict(
                            snapshot_id=ident,
                            module=module,
                            params={"seed": seed},
                            deep_link="#labs/" + module,
                            role="development",
                            go2_eligible=False,
                            control=dict(
                                kind="null_twin" if null else "none",
                                cluster_id=block,
                                twin_snapshot_id=twin,
                            ),
                        )
                        e = s.make_entry(
                            root,
                            job,
                            png,
                            png,
                            data,
                            {"fixture": "1"},
                            (0, 0, 288, 288),
                            [],
                            {"ocr": "passed"},
                            ["withheld secret"],
                        )
                        e.update(status="checkable", go2_eligible=True)
                        e["data_ref"].update(
                            seed=seed,
                            source_block_id=block + ("-null" if null else ""),
                            role=role,
                            support={
                                "population": module + ("-null" if null else ""),
                                "start": cluster * 30
                                + ["discovery", "replication", "donor"].index(role)
                                * 10,
                                "stop": cluster * 30
                                + ["discovery", "replication", "donor"].index(role) * 10
                                + 10,
                            },
                        )
                        entries.append(e)
        strata.append(st)
    template = small_card().to_dict()
    template.update(status="draft", artifacts=[], judgments=[], history=[], revision=1)
    template["observer"] = {
        "id": "human:fixture-author",
        "kind": "human",
        "blinded": True,
    }
    template["prior_plausibility"]["by"] = "human:fixture-author"
    template["content_hash"] = card_hash(template)
    generic = {
        k: deepcopy(template[k])
        for k in ("claim", "testable_form", "prediction", "resemblance_target")
    }
    config = dict(
        seed=20260928,
        pilot=views == 1,
        views=views,
        slots=3,
        retries=0,
        strata=strata,
        development_blocks=[],
        checks={"zero spacings": template},
        image_free={"zero spacings": [deepcopy(generic) for _ in range(views * 3)]},
        owner_questions={"Q2": None, "Q3": None, "Q4": None, "Q5": None, "Q6": None},
    )
    return {"schema": s.SCHEMA, "snapshots": entries}, config


def replays(plan):
    generic = next(iter(plan.to_dict()["config"]["image_free"].values()))[:3]
    return {
        j["id"]: (
            Replay((reply(), reply(2))),
            Replay((mutate_reply(content={"cards": generic}),)),
        )
        for j in plan.to_dict()["jobs"]
        if j["arm"] != "image_free"
    }
