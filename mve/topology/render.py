"""Pinned Pillow polygon lines; cut only the recorded exact underpass gaps."""

from io import BytesIO
from PIL import Image, ImageDraw
from mve.topology.geometry import segments, decode


def render(s):
    decode(s)
    rows = segments(s)
    points = [p for c in s.components for p in c]
    low = [min(p[i] for p in points) for i in (0, 1)]
    high = [max(p[i] for p in points) for i in (0, 1)]
    scale = 480 / float(max(high[i] - low[i] for i in (0, 1)))

    def pixel(p):
        return (16 + float(p[0] - low[0]) * scale, 496 - float(p[1] - low[1]) * scale)

    image = Image.new("RGB", (512, 512), "white")
    draw = ImageDraw.Draw(image)
    for ci, i, a, b in rows:
        gaps = sorted(
            (g.start, g.end) for g in s.gaps if (ci, i) == (g.component, g.segment)
        )
        cuts = [0] + [v for gap in gaps for v in gap] + [1]
        for start, end in zip(cuts[::2], cuts[1::2]):
            endpoints = [
                tuple(a[k] + t * (b[k] - a[k]) for k in (0, 1)) for t in (start, end)
            ]
            draw.line([pixel(p) for p in endpoints], fill="black", width=3)
    buffer = BytesIO()
    image.save(buffer, format="PNG", compress_level=9)
    return buffer.getvalue()
