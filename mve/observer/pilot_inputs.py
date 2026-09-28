"""Reviewed WO-1 development views; never invent independent blocks or donors."""

from io import BytesIO
import hashlib
import json
from pathlib import Path
import random
from PIL import Image
from mve.observer.card import digest
from mve.observer.design import ARMS, require
from mve.observer.snapshots import inside, sha256, png_chunks

ROOT = Path(__file__).resolve().parents[2]
INPUTS = Path(__file__).with_name("fixtures") / "wo6"
MODULES = ("spectral", "field-dyson", "polar-ulam", "space-08")
INPUT_TOKENS = 16384
OUTPUT_TOKENS = 1024
CALL_CAP = 24
SEED = 20260928


def manifest():
    return json.loads((INPUTS / "manifest.json").read_text())


def image_bytes(ident):
    entry = next(e for e in manifest()["snapshots"] if e["snapshot_id"] == ident)
    path = inside(INPUTS, entry["png_blinded"]["path"])
    require(sha256(path) == entry["png_blinded"]["sha256"], "blinded PNG hash mismatch")
    require(
        set(png_chunks(path.read_bytes())) <= {"IHDR", "IDAT", "IEND"},
        "PNG metadata not stripped",
    )
    with Image.open(path) as im:
        require(
            im.format == "PNG"
            and im.size == (entry["png_blinded"]["w"], entry["png_blinded"]["h"]),
            "PNG dimensions mismatch",
        )
        im = im.convert("RGB")
        im.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
        out = BytesIO()
        im.save(out, format="PNG")
    return out.getvalue()


def load_plan():
    m = manifest()
    require(len(m["snapshots"]) == 8, "fixed eight reviewed WO-1 views required")
    capture = json.loads((INPUTS / "receipt.json").read_text())
    repeat = json.loads((INPUTS / "repeat-verification.json").read_text())
    require(
        capture["capture"] == "captured"
        and capture["source_repos_unchanged"]
        and repeat["passed"],
        "reviewed repeated capture required",
    )
    images, clusters, jobs = {}, [], []
    for e in m["snapshots"]:
        require(
            e["data_ref"]["role"] == "development" and not e["go2_eligible"],
            "WO-1 source roles changed",
        )
        require(
            e["png_blinded"]["caption_free"] and e["png_blinded"]["metadata_stripped"],
            "blinding required",
        )
        require(
            sha256(inside(INPUTS, e["data_ref"]["path"])) == e["data_ref"]["sha256"],
            "source data hash mismatch",
        )
        data = image_bytes(e["snapshot_id"])
        with Image.open(BytesIO(data)) as im:
            size = list(im.size)
        images[e["snapshot_id"]] = dict(
            original_size=[e["png_blinded"]["w"], e["png_blinded"]["h"]],
            delivered_size=size,
            original_sha256=e["png_blinded"]["sha256"],
            delivered_sha256=hashlib.sha256(data).hexdigest(),
        )
    for module in MODULES:
        real = next(
            e
            for e in m["snapshots"]
            if e["module"] == module and e["control"]["kind"] == "none"
        )
        twin = next(
            e
            for e in m["snapshots"]
            if e["snapshot_id"] == real["control"]["twin_snapshot_id"]
        )
        require(
            twin["control"]["kind"] == "null_twin"
            and twin["control"]["twin_snapshot_id"] == real["snapshot_id"]
            and twin["module"] == module,
            "twin mismatch",
        )
        cid = digest({"module": module, "seed": SEED})[:16]
        clusters.append(
            dict(
                id=cid,
                module=module,
                stratum=real["data_ref"]["stratum"],
                independent=False,
            )
        )
        for arm in ARMS:
            ident = digest({"cluster": cid, "arm": arm})[:16]
            jobs.append(
                dict(
                    id=ident,
                    cluster=cid,
                    module=module,
                    arm=arm,
                    slots=3,
                    snapshot_id=real["snapshot_id"]
                    if arm == "real"
                    else twin["snapshot_id"]
                    if arm == "null_twin"
                    else None,
                    source_id=twin["snapshot_id"]
                    if arm == "null_twin"
                    else real["snapshot_id"],
                )
            )
    random.Random(SEED).shuffle(jobs)
    plan = dict(
        schema="mve-wo6-descriptive-design-v1",
        seed=SEED,
        clusters=clusters,
        jobs=jobs,
        images=images,
        planned_calls=CALL_CAP,
        call_cap=CALL_CAP,
        retries=0,
        independent_clusters=0,
        contrasts=0,
        input_tokens=INPUT_TOKENS,
        output_tokens=OUTPUT_TOKENS,
        worst_case_micro_usd=147456,
        second_observer={"status": "SKIPPED", "reason": "owner Q2 unanswered"},
        input_assumption="16384 tokens per call includes resized blinded pixels, at most 2048 UTF-8 prompt bytes and hidden overhead. Conservative engineering allowance; vendor image tokenization is unverified, not a server-enforced input bound.",
        limitations=[
            "Four development pairs, not the planned ten independent clusters; source catalogues overlap.",
            "No disjoint replication, same-stratum donors or contrast blocks exist in reviewed WO-1. Shuffled slots stay unavailable; no relabelling or redrawing.",
            "GO2 cannot pass: fewer than 20 independent clusters; all results descriptive only.",
            "No second observer, owner cards, relay, adoption, GO3 or novelty claim.",
        ],
    )
    return {**plan, "sha256": digest(plan)}
