"""RFC 6902 patch mechanics, with record editing restrictions applied by the caller."""

from copy import deepcopy
from mve.errors import RecordError


def tokens(path):
    if not isinstance(path, str) or not path.startswith("/"):
        raise RecordError("patch must use an absolute non-root JSON Pointer")
    parts = path[1:].split("/")
    for part in parts:
        for i, char in enumerate(part):
            if char == "~" and (i + 1 == len(part) or part[i + 1] not in "01"):
                raise RecordError("invalid JSON Pointer escape")
    return [p.replace("~1", "/").replace("~0", "~") for p in parts]


def index(container, key, append=False):
    if isinstance(container, list):
        if key == "-" and append:
            return len(container)
        if not key.isdigit() or (len(key) > 1 and key.startswith("0")):
            raise RecordError("invalid array index")
        value = int(key)
        if value >= len(container) + (1 if append else 0):
            raise RecordError("array index out of range")
        return value
    if not isinstance(container, dict):
        raise RecordError("patch traverses a scalar")
    return key


def location(data, path):
    parts = tokens(path)
    node = data
    for part in parts[:-1]:
        node = node[index(node, part)]
    return node, index(node, parts[-1], append=True)


def read(data, path):
    node = data
    for part in tokens(path):
        node = node[index(node, part)]
    return deepcopy(node)


def apply_patch(data, patch):
    result = deepcopy(data)
    for change in patch:
        op = change.get("op")
        path = change.get("path")
        if op == "test":
            if read(result, path) != change["value"]:
                raise RecordError("patch test failed")
            continue
        if op in ("copy", "move"):
            source = change["from"]
            value = read(result, source)
            if op == "move":
                if tokens(path)[: len(tokens(source))] == tokens(source):
                    raise RecordError("cannot move a node into itself")
                parent, key = location(result, source)
                del parent[key]
        elif op in ("add", "replace"):
            value = deepcopy(change["value"])
        elif op != "remove":
            raise RecordError("unknown patch operation")
        parent, key = location(result, path)
        if op in ("remove", "replace"):
            if isinstance(parent, dict) and key not in parent:
                raise RecordError("missing patch member")
            if isinstance(parent, list) and key >= len(parent):
                raise RecordError("missing patch item")
            if op == "remove":
                del parent[key]
                continue
        if op in ("add", "copy", "move") and isinstance(parent, list):
            parent.insert(key, value)
        else:
            parent[key] = value
    return result
