"""Offline C1 records, bounded archives, blinding and read-only isolation receipts.

The initial four pairs are development views, NOT disjoint GO2 clusters. Owner
manifests contain answers; model delivery must use only the re-encoded blind PNG.
"""

from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tarfile

from PIL import Image, ImageChops, ImageDraw

from mve.observer.card import digest

SCHEMA = "oae-mve-snapshots-v1"
PNG_REPEAT_TOLERANCE = {
    "channels": "RGBA8",
    "channel_difference_threshold": 8,
    "channel_scale": 255,
    "max_pixels_over_threshold_fraction": 0.001,
    "require_same_dimensions": True,
}
COMMITS = {
    "atlas": "97b1e48cb1075aea431cf754cc84f2eeabb3dfb9",
    "lab": "c81510cd29b0fc666b1f171a9604a51be9661576",
}
PATHS = {
    "atlas": (
        "vendor/zeta-explorer/dist",
        "rh_evidence/labs",
        "data/riemann/evidence_atlas/inputs/lab_snapshots.json",
    ),
    "lab": ("dist", "scripts"),
}
MODULES = {
    "spectral": {
        "seed": 20260926,
        "family": "zero spacings",
        "params": {"spectralCount": 100, "matrixSize": 64},
        "deep_link": "#labs/spectral",
        "selector": "#spectralPlot",
    },
    "field-dyson": {
        "seed": 20260926,
        "family": "zero spacings",
        "params": {"animate": False},
        "deep_link": "#labs/field-dyson",
        "selector": "#fieldSide",
    },
    "polar-ulam": {
        "seed": 20260925,
        "family": "primes",
        "params": {"N": 30000, "overlay": False},
        "deep_link": "#labs/polar-ulam",
        "selector": "#polarPlot",
    },
    "space-08": {
        "seed": 2026,
        "family": "primes",
        "params": {
            "N": 100000,
            "view": "viviani",
            "alpha": 1,
            "beta": 1,
            "q": 44,
            "colour": "class",
        },
        "deep_link": "#labs/space-primesphere",
        "selector": "#mathboxScene canvas",
    },
}
BACKGROUND = "#091113"


def sha256(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def inside(root, relative):
    root = Path(root).resolve()
    p = Path(relative)
    if p.is_absolute() or ".." in p.parts or not p.parts:
        raise ValueError("unsafe relative path")
    target = (root / p).resolve()
    if not target.is_relative_to(root):
        raise ValueError("path escapes root through symlink")
    return target


def tree_listing(root):
    root = Path(root)
    files = [root] if root.is_file() else sorted(root.rglob("*"))
    rows = []
    for p in files:
        st = p.lstat()
        row = dict(
            path=p.name if p == root else p.relative_to(root).as_posix(),
            mode=st.st_mode,
            size=st.st_size,
            mtime_ns=st.st_mtime_ns,
        )
        if p.is_symlink():
            row["link"] = os.readlink(p)
        elif p.is_file():
            row["sha256"] = sha256(p)
        rows.append(row)
    return rows


def tree_bytes(root):
    return sum(
        p.stat().st_size
        for p in Path(root).rglob("*")
        if p.is_file() and not p.is_symlink()
    )


def disk_guard(generated, incoming):
    # Each archive, browser launch and screenshot batch is guarded, even <10 MiB.
    if shutil.disk_usage("/")[2] < 5 * 1024**3:
        raise ValueError("less than 5 GiB free; abort write")
    if tree_bytes(generated) + incoming >= 500 * 1024**2:
        raise ValueError("generated would reach 500 MiB; abort write")


def extract_archive(stream, dest, allowed, limit=64 * 1024**2):
    total = 0
    with tarfile.open(fileobj=stream, mode="r|") as archive:
        for member in archive:
            p = Path(member.name)
            # git archive includes ancestor directories for the pathspecs.
            permitted = any(
                p == Path(a)
                or Path(a) in p.parents
                or (member.isdir() and p in Path(a).parents)
                for a in allowed
            )
            if not permitted or not (member.isdir() or member.isfile()):
                raise ValueError("archive path/type outside allowlist")
            target = inside(dest, member.name)
            total += member.size
            if total > limit:
                raise ValueError("archive exceeds byte limit")
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as source, target.open("xb") as out:
                    shutil.copyfileobj(source, out)


def archive_repo(repo, name, dest, generated):
    """Only the two hard-coded commits/pathspecs; never archive an entire repo."""
    disk_guard(generated, 64 * 1024**2)
    cmd = [
        "git",
        "--no-optional-locks",
        "-C",
        str(repo),
        "archive",
        COMMITS[name],
        "--",
        *PATHS[name],
    ]
    if Path(dest).exists():
        raise ValueError("archive destination must be new")
    Path(dest).mkdir(parents=True)
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as p:
        try:
            extract_archive(p.stdout, dest, PATHS[name])
        except BaseException:
            p.kill()
            raise
        if p.wait():
            raise ValueError("git archive failed")


def isolation_state(repos):
    result = {}
    for name, repo in repos.items():
        result[name] = {
            "trees": {sub: tree_listing(Path(repo) / sub) for sub in PATHS[name]},
            "status": subprocess.check_output(
                [
                    "git",
                    "--no-optional-locks",
                    "-C",
                    str(repo),
                    "status",
                    "--ignored",
                    "--porcelain=v1",
                    "--untracked-files=all",
                ],
                text=True,
            ),
        }
    return result


def capture_jobs():
    jobs = []
    for module, config in MODULES.items():
        ids = [
            digest({"module": module, "arm": arm, "packet": "WO-1"})[:24]
            for arm in ("real", "null")
        ]
        for i, ident in enumerate(ids):
            jobs.append(
                dict(
                    snapshot_id=ident,
                    module=module,
                    params={**deepcopy(config["params"]), "seed": config["seed"]},
                    deep_link=config["deep_link"],
                    role="development",
                    go2_eligible=False,
                    control=dict(
                        kind="null_twin" if i else "none",
                        cluster_id=f"development-{module}",
                        twin_snapshot_id=ids[1 - i],
                    ),
                )
            )
    return jobs


def png_chunks(data):
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not PNG")
    pos, chunks = 8, []
    while pos < len(data):
        if pos + 12 > len(data):
            raise ValueError("truncated PNG")
        size = struct.unpack(">I", data[pos : pos + 4])[0]
        chunks.append(data[pos + 4 : pos + 8].decode("ascii"))
        pos += size + 12
    if pos != len(data) or chunks[-1:] != ["IEND"]:
        raise ValueError("truncated PNG")
    return chunks


def _box(box, size):
    if len(box) != 4 or not all(type(x) is int for x in box):
        raise ValueError("integer crop/mask box required")
    left, t, r, b = box
    if not (0 <= left < r <= size[0] and 0 <= t < b <= size[1]):
        raise ValueError("box outside image")
    return box


def blind_png(data, crop_box, masks):
    with Image.open(io.BytesIO(data)) as src:
        crop = src.convert("RGB").crop(_box(crop_box, src.size))
    # New image rather than copying Pillow info/EXIF/ICC from the source.
    clean = Image.new("RGB", crop.size)
    clean.paste(crop)
    draw = ImageDraw.Draw(clean)
    for mask in masks:
        left, t, r, b = _box(mask, clean.size)
        draw.rectangle((left, t, r - 1, b - 1), fill=BACKGROUND)
    out = io.BytesIO()
    clean.save(out, format="PNG", optimize=True)
    return out.getvalue()


def assert_regions_clean(data, masks):
    with Image.open(io.BytesIO(data)) as im:
        for mask in masks:
            tile = im.convert("RGB").crop(_box(mask, im.size))
            if tile.tobytes() != Image.new("RGB", tile.size, BACKGROUND).tobytes():
                raise ValueError("text region is not blank")


def leakage_report(path, withheld, *, executable, run=subprocess.run):
    report = {
        "ocr": "unavailable",
        "limitation": "No offline OCR: source-audited canvas-only crop, text-call suppression "
        "and fixed pixel masks do not prove absence of raster/WebGL text.",
    }
    if executable:
        result = run(
            [executable, str(path), "stdout", "--psm", "11"],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )

        def normal(text):
            return " ".join(re.findall(r"\w+", text.casefold()))

        found = normal(result.stdout)
        if any(normal(w) and normal(w) in found for w in withheld):
            raise ValueError("OCR text leakage in blinded image")
        report = {
            "ocr": "passed",
            "limitation": "OCR can miss text; pixel and source rules also required.",
        }
    return report


def image_ref(root, path):
    with Image.open(path) as im:
        w, h = im.size
    return dict(
        path=Path(path).relative_to(root).as_posix(), sha256=sha256(path), w=w, h=h
    )


def compare_png(first, second):
    """Count pixels whose largest absolute RGBA8 channel delta exceeds 8."""
    with Image.open(first) as a, Image.open(second) as b:
        metrics = {
            "first_size": list(a.size),
            "repeat_size": list(b.size),
            "same_dimensions": a.size == b.size,
            "total_pixels": a.width * a.height,
            "pixels_over_threshold": None,
            "pixels_over_threshold_fraction": None,
            "max_channel_difference": None,
            "passed": False,
        }
        if a.size != b.size:
            return metrics
        bands = ImageChops.difference(a.convert("RGBA"), b.convert("RGBA")).split()
        largest = bands[0]
        for band in bands[1:]:
            largest = ImageChops.lighter(largest, band)
        histogram = largest.histogram()
    threshold = PNG_REPEAT_TOLERANCE["channel_difference_threshold"]
    count = sum(histogram[threshold + 1 :])
    fraction = count / metrics["total_pixels"]
    metrics.update(
        pixels_over_threshold=count,
        pixels_over_threshold_fraction=fraction,
        max_channel_difference=max(i for i, n in enumerate(histogram) if n),
        passed=fraction <= PNG_REPEAT_TOLERANCE["max_pixels_over_threshold_fraction"],
    )
    return metrics


def snapshot_hash(entry):
    """Content identity binds exact retained bytes and the declared repeat rule."""
    return digest(
        {
            "capture_id": entry["snapshot_id"],
            "artifact_sha256": {
                kind: entry[kind]["sha256"]
                for kind in ("png_full", "png_blinded", "data_ref")
            },
            "png_repeat_tolerance": entry["png_repeat_tolerance"],
        }
    )


def make_entry(root, job, full, blind, data, versions, crop, masks, leakage, withheld):
    e = deepcopy(job)
    cfg = MODULES[e["module"]]
    e.update(
        params_sha256=digest(e["params"]),
        lab_commit=dict(COMMITS),
        data_ref=dict(
            path=Path(data).relative_to(root).as_posix(),
            sha256=sha256(data),
            generator="archived lab numerical module; adapter-v1",
            seed=cfg["seed"],
            source_block_id=e["snapshot_id"] + "-data",
            stratum=e["module"] + " × " + cfg["family"],
            role=e.pop("role"),
        ),
        png_full=image_ref(root, full),
        png_blinded=image_ref(root, blind),
        withheld_text=withheld,
        renderer_versions=versions,
        status="development_only",
        limitations=[
            "Overlapping small catalogues across modules; no disjoint D/R/donor allocation.",
            "Native renderer adapted for single-source/palette-matched display; not a baseline calibration.",
        ],
    )
    e["png_blinded"].update(
        crop_box=list(crop),
        masks=[list(x) for x in masks],
        caption_free=True,
        metadata_stripped=True,
        chunks=png_chunks(Path(blind).read_bytes()),
        leakage=leakage,
    )
    e["png_repeat_tolerance"] = deepcopy(PNG_REPEAT_TOLERANCE)
    e["snapshot_sha256"] = snapshot_hash(e)
    return e


def validate_manifest(manifest, root):
    """Validate records AND local bytes; a missing/full uncommitted artifact fails."""
    try:
        if manifest["schema"] != SCHEMA or not manifest["snapshots"]:
            raise ValueError("invalid manifest schema/empty capture")
        json.dumps(manifest, allow_nan=False)
        entries = manifest["snapshots"]
        by_id = {e["snapshot_id"]: e for e in entries}
        if len(by_id) != len(entries):
            raise ValueError("duplicate snapshot id")
        required = {
            "snapshot_id",
            "module",
            "deep_link",
            "params",
            "params_sha256",
            "lab_commit",
            "data_ref",
            "control",
            "png_full",
            "png_blinded",
            "withheld_text",
            "renderer_versions",
            "status",
            "go2_eligible",
        }
        for e in entries:
            if (
                not required <= e.keys()
                or not isinstance(e["deep_link"], str)
                or not e["deep_link"].startswith("#labs/")
            ):
                raise ValueError("required C1 fields missing")
            ref = e["data_ref"]
            if (
                not all(
                    ref.get(k)
                    for k in ("generator", "source_block_id", "stratum", "role")
                )
                or ref.get("seed") != e["params"]["seed"]
            ):
                raise ValueError("incomplete source data identity")
            if e["status"] not in ("development_only", "not_checkable"):
                raise ValueError("invalid snapshot status")
            if e["module"] not in MODULES or e["params_sha256"] != digest(e["params"]):
                raise ValueError("params hash/module mismatch")
            if (
                e["lab_commit"] != COMMITS
                or not e["renderer_versions"]
                or not e["withheld_text"]
            ):
                raise ValueError("missing provenance")
            if e["go2_eligible"] or e["data_ref"]["role"] != "development":
                raise ValueError("initial views cannot be GO2 clusters")
            for kind in ("data_ref", "png_full", "png_blinded"):
                ref = e[kind]
                if kind == "data_ref" and ref["sha256"] is None and ref["path"] is None:
                    if e["status"] != "not_checkable":
                        raise ValueError("missing data must be not_checkable")
                    continue
                p = inside(root, ref["path"])
                if sha256(p) != ref["sha256"]:
                    raise ValueError("artifact hash mismatch")
                if kind.startswith("png"):
                    with Image.open(p) as im:
                        if list(im.size) != [ref["w"], ref["h"]]:
                            raise ValueError("image size mismatch")
            blind = e["png_blinded"]
            data = inside(root, blind["path"]).read_bytes()
            if (
                blind["caption_free"] is not True
                or blind["metadata_stripped"] is not True
            ):
                raise ValueError("blinding missing")
            if set(png_chunks(data)) != {"IHDR", "IDAT", "IEND"}:
                raise ValueError("PNG contains ancillary metadata")
            if blind["chunks"] != png_chunks(data):
                raise ValueError("chunk receipt mismatch")
            _box(blind["crop_box"], (e["png_full"]["w"], e["png_full"]["h"]))
            left, t, r, b = blind["crop_box"]
            if (r - left, b - t) != (blind["w"], blind["h"]):
                raise ValueError("crop dimensions mismatch")
            assert_regions_clean(data, blind["masks"])
            if e["png_repeat_tolerance"] != PNG_REPEAT_TOLERANCE:
                raise ValueError("unsupported PNG repeat tolerance")
            if e["snapshot_sha256"] != snapshot_hash(e):
                raise ValueError("snapshot identity hash mismatch")
            twin = by_id[e["control"]["twin_snapshot_id"]]
            if (
                twin["control"]["twin_snapshot_id"] != e["snapshot_id"]
                or twin["module"] != e["module"]
                or twin["params"] != e["params"]
                or twin["renderer_versions"] != e["renderer_versions"]
                or {twin["control"]["kind"], e["control"]["kind"]}
                != {"none", "null_twin"}
                or twin["control"]["cluster_id"] != e["control"]["cluster_id"]
                or twin["png_blinded"]["crop_box"] != blind["crop_box"]
                or twin["png_blinded"]["masks"] != blind["masks"]
            ):
                raise ValueError("control twin mismatch")
    except (KeyError, TypeError, OSError) as exc:
        raise ValueError("incomplete snapshot manifest/artifacts") from exc
    return manifest


def card_source(entry):
    if entry["status"] == "not_checkable" or not entry["data_ref"]["sha256"]:
        raise ValueError("source not checkable")
    return dict(
        snapshot_id=snapshot_hash(entry),
        png_sha256=entry["png_blinded"]["sha256"],
        data_sha256=entry["data_ref"]["sha256"],
    )


def read_index(index, root):
    entries = deepcopy(json.loads(Path(index).read_text())["snapshots"])
    for e in entries:
        cap = e["capture"]
        # The allowed archive omits the atlas capture tool/hash algorithm.
        # Preserve its claim without treating it as our canonical C1 params hash.
        e["adapter_params_sha256"] = digest(e["params"])
        e["atlas_params_hash_status"] = "unverified_algorithm_not_in_allowed_archive"
        p = inside(root, cap["png"]["path"])
        e["availability"] = "not_in_allowed_archive"
        if p.exists():
            if sha256(p) != cap["png"]["sha256"]:
                raise ValueError("atlas PNG hash mismatch")
            e["availability"] = "verified"
    return entries
