"""Pinned raster recipe; pixel coordinates are separate from exact mathematical truth."""

from io import BytesIO
import math
from mve.identity import digest
from PIL import Image, ImageDraw, ImageFont, __version__ as PILLOW_VERSION
from mve.generator.exact import ExactEvaluator


EDGES = (("A", "B"), ("B", "D"), ("D", "E"), ("E", "F"), ("F", "A"), ("A", "C"))


def oriented_points(construction):
    exact = ExactEvaluator(construction["coordinates"])
    code = int(digest(construction["generator"]), 16)
    angle = (code % 1000003) / 1000003 * 2 * math.pi
    cosine, sine = math.cos(angle), math.sin(angle)
    points = {
        name: [cosine * float(x) - sine * float(y), sine * float(x) + cosine * float(y)]
        for name, (x, y) in exact.points.items()
    }
    return points, 192 + ((code >> 20) % 33)


def pixel_projection(construction):
    points, extent = oriented_points(construction)
    low = [min(p[i] for p in points.values()) for i in (0, 1)]
    high = [max(p[i] for p in points.values()) for i in (0, 1)]
    span = max(high[i] - low[i] for i in (0, 1)) or 1
    pixels = {
        name: [
            round((288 - extent) / 2 + extent * (p[0] - low[0]) / span, 6),
            round((288 + extent) / 2 - extent * (p[1] - low[1]) / span, 6),
        ]
        for name, p in points.items()
    }
    if construction["control"] == "not_to_scale":
        pixels["C"][1] = max(16, min(272, pixels["C"][1] - 40))
    elif construction["control"] == "adversarial_negative":
        pixels["C"] = [(pixels["A"][i] + pixels["B"][i]) / 2 for i in (0, 1)]
    return pixels


def render(construction, *, style="thin"):
    if style not in {"thin", "bold"}:
        raise ValueError("unsupported render style")
    pixels = pixel_projection(construction)
    image = Image.new("RGB", (288, 288), "white")
    draw = ImageDraw.Draw(image)
    for a, b in EDGES:
        draw.line(
            [tuple(pixels[a]), tuple(pixels[b])],
            fill="black",
            width=1 if style == "thin" else 3,
        )
    grouped = {}
    for name, xy in pixels.items():
        grouped.setdefault(tuple(xy), []).append(name)
    for (x, y), names in grouped.items():
        draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill="black")
        draw.text(
            (x + 4, y - 14),
            ",".join(names),
            fill="black",
            font=ImageFont.load_default(),
        )
    buffer = BytesIO()
    image.save(buffer, format="PNG", compress_level=9)
    metadata = {
        "schema": "mve-render-v1",
        "pixels": pixels,
        "width": 288,
        "height": 288,
        "renderer": "pillow-lines-v2",
        "pillow_version": PILLOW_VERSION,
        "style": style,
        "render_pinned": False,
        "control": construction["control"],
    }
    return buffer.getvalue(), metadata
