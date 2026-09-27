"""Portable, content-addressed local artifacts."""

from hashlib import sha256
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]


def digest_file(path):
    digest = sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def digest_json(value):
    return sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def resolve_path(value):
    if value.startswith("$HOME/"):
        return Path.home() / value[6:]
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def portable(value):
    """Also normalizes paths embedded in historical stdout and command strings."""
    if isinstance(value, str):
        return value.replace(str(ROOT) + "/", "").replace(str(Path.home()), "$HOME")
    if isinstance(value, dict):
        return {portable(k): portable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [portable(v) for v in value]
    return value


def verify_files(entries):
    for entry in entries:
        if digest_file(resolve_path(entry["path"])) != entry["sha256"]:
            raise ValueError("artifact hash mismatch: " + entry["path"])


def load_lock(path=None):
    path = Path(path or ROOT / "mve/classifier/lock.json")
    data = json.loads(path.read_text())
    verify_files(data["artifacts"])
    data["sha256"] = digest_file(path)
    return data
