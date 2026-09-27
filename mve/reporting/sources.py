"""Read Git objects, not mutable working files; retain byte-level provenance."""

import hashlib
import json
import os
from pathlib import PurePosixPath
import subprocess


def relative(path):
    value = PurePosixPath(path)
    if (
        value.is_absolute()
        or ".." in value.parts
        or str(value) != path
        or not value.parts
    ):
        raise ValueError("evidence paths must be canonical repository-relative paths")
    return path


class Evidence:
    def __init__(self, root, revision):
        self.root = root
        self.revision = (
            self._git(
                "rev-parse", "--verify", "--end-of-options", revision + "^{commit}"
            )
            .decode()
            .strip()
        )
        self.paths = set(
            self._git("ls-tree", "-r", "--name-only", self.revision)
            .decode()
            .splitlines()
        )
        self.sources = {}
        self.missing = []

    def _git(self, *args):
        result = subprocess.run(
            ["git", "-c", "protocol.allow=never", "-C", str(self.root), *args],
            capture_output=True,
            env={**os.environ, "GIT_NO_LAZY_FETCH": "1", "GIT_OPTIONAL_LOCKS": "0"},
        )
        if result.returncode:
            raise ValueError("committed evidence could not be read")
        return result.stdout

    def read(self, path):
        relative(path)
        if path not in self.paths:
            raise ValueError("required committed evidence missing: " + path)
        blob = self._git("show", self.revision + ":" + path)
        self.sources[path] = {"sha256": hashlib.sha256(blob).hexdigest()}
        return blob

    def json(self, path):
        return json.loads(self.read(path))

    def optional(self, path):
        relative(path)
        if path not in self.paths:
            self.missing.append(path)
            return None
        return self.json(path)
