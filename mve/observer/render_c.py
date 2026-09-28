"""WO-6c-only response patches. Archived renderer bytes remain untouched."""

import mimetypes
from urllib.parse import urlsplit, unquote
from mve.observer import snapshot_render as old, snapshots as s

PATCHES = {
    "research.js": [
        (
            "function line(c,x1,y1,x2,y2,color,width=1){",
            "function line(c,x1,y1,x2,y2,color,width=1){if(window.__mveBlind)return;",
        )
    ],
    "field-phase3-overlay.js": [
        (
            "c.strokeRect(x0, y0, x1 - x0, y1 - y0);",
            "if(!window.__mveBlind)c.strokeRect(x0, y0, x1 - x0, y1 - y0);",
        ),
        (
            "function line(c, pts, color, width = 1.2, dash = []) {",
            "function line(c, pts, color, width = 1.2, dash = []) { if(window.__mveBlind)return;",
        ),
        (
            "bars(c, L, s.pair, 0.1, WHITE + '66');",
            "if(!window.__mveBlind)bars(c, L, s.pair, 0.1, WHITE + '66');",
        ),
    ],
    "prime-sphere.js": [
        ("    guides(o, d);", "    if(!window.__mveBlind)guides(o, d);"),
        (
            "const plain = synthetic ? SYNTHETIC_PLAIN : PLAIN, colourOf = i => o.colour === 'class' ? classColour(sel.n[i] % o.q, o.q) : plain;",
            "const plain = PLAIN, colourOf = i => PLAIN;",
        ),
    ],
}


def transform(name, text):
    text = old.block_transform(name, old.transform(name, text))
    for before, after in PATCHES.get(name, []):
        if text.count(before) != 1:
            raise ValueError("WO-6c renderer anchor drift")
        text = text.replace(before, after)
    return text


def handler(dist):
    def handle(route, request):
        url = urlsplit(request.url)
        if (
            url.scheme != "https"
            or url.netloc != "mve.invalid"
            or request.method != "GET"
        ):
            route.abort()
            return
        try:
            path = s.inside(dist, unquote(url.path).lstrip("/") or "index.html")
            raw = path.read_bytes()
        except (ValueError, OSError):
            route.abort()
            return
        if path.suffix == ".js":
            raw = transform(path.name, raw.decode()).encode()
        route.fulfill(
            status=200,
            body=raw,
            content_type=mimetypes.guess_type(path.name)[0]
            or "application/octet-stream",
            headers={"Cache-Control": "no-store"},
        )

    return handle


def crop(module, raw):
    # WO-1's Dyson canvas has an unrelated pair-correlation panel on the left.
    # Remove that whole panel identically, after masking at the native resolution.
    from io import BytesIO
    from PIL import Image

    if module != "field-dyson":
        return raw
    with Image.open(BytesIO(raw)) as im:
        out = BytesIO()
        im.crop((im.width // 2, 0, im.width, im.height)).save(out, format="PNG")
    return out.getvalue()
