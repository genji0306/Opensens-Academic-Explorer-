"""Pinned natural-feature statistics on numbers, never on PNGs.

Spatial coordinates use the pinned renderer formula and camera projection,
computed from exported indices; no pixels enter a statistic.
"""

import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks
from scipy.stats import spearmanr, ks_2samp
from mve.observer import native_nulls as native

TAGS = (
    "density_linear_x",
    "density_linear_y",
    "density_radial",
    "modality_x",
    "modality_y",
    "reflection_x",
    "reflection_y",
    "spacing_ks",
)
ALPHA = 0.05


def ulam(n):
    n = np.asarray(n, dtype=float)
    k = np.ceil((np.sqrt(n) - 1) / 2)
    t = n - (2 * k - 1) ** 2
    x = np.where(
        t <= 2 * k,
        k,
        np.where(t <= 4 * k, 3 * k - t, np.where(t <= 6 * k, -k, t - 7 * k)),
    )
    y = np.where(
        t <= 2 * k, t - k, np.where(t <= 4 * k, k, np.where(t <= 6 * k, 5 * k - t, -k))
    )
    x = np.where(n == 1, 0, x)
    y = np.where(n == 1, 0, y)
    return np.column_stack((x, y))


def coordinates(module, data):
    if module in ("spectral", "field-dyson"):
        values = (
            np.asarray(data["values"], dtype=float)
            if module == "spectral"
            else native.gaps(module, data["values"])
        )
        return checked(values[:, None]), (0.0, 3.0), "source_gaps"
    n = np.asarray(data["values"], dtype=float)
    if n.ndim != 1 or len(n) < 4 or not np.isfinite(n).all() or np.any(np.diff(n) <= 0):
        raise ValueError("invalid exported indices")
    extent = data.get("extent", data.get("N", data.get("options", {}).get("N", 100000)))
    if module == "polar-ulam":
        p = ulam(n) / np.ceil((np.sqrt(extent) - 1) / 2)
    elif module == "space-08":
        o = data.get("options", {})
        if any(
            o.get(k, v) != v
            for k, v in [("view", "viviani"), ("alpha", 1), ("beta", 1)]
        ):
            raise ValueError("unsupported coordinate parameters")
        world = (
            np.column_stack(
                (n * np.sin(n) * np.cos(n), n * np.cos(n), -n * np.sin(n) ** 2)
            )
            * 1.1
            / extent
        )
        camera = np.array([0.55, 0.45, 3.5])
        forward = -camera / np.linalg.norm(camera)
        right = np.cross(forward, [0, 1, 0])
        right /= np.linalg.norm(right)
        up = np.cross(right, forward)
        relative = world - camera
        p = np.column_stack((relative @ right, relative @ up)) / (
            (relative @ forward)[:, None] * np.tan(np.deg2rad(21))
        )
    else:
        raise ValueError("unknown module")
    return p, (-1.0, 1.0), "display_coordinates"


def tags(module):
    return (
        tuple(t for t in TAGS if not t.endswith("_y"))
        if module in ("spectral", "field-dyson")
        else TAGS[:-1]
    )


def checked(points):
    p = np.asarray(points, dtype=float)
    if (
        p.ndim != 2
        or len(p) < 4
        or p.shape[1] not in (1, 2)
        or not np.isfinite(p).all()
    ):
        raise ValueError("finite numeric coordinates required")
    return p


def value(points, tag, support):
    p = checked(points)
    if tag not in TAGS or tag == "spacing_ks":
        raise ValueError("unknown scalar statistic")
    axis = 1 if tag.endswith("_y") else 0
    if axis >= p.shape[1]:
        raise ValueError("axis unavailable")
    x = p[:, axis]
    if tag.startswith("density_"):
        # Equal-volume cells; local density is a count, not radial shell count.
        if p.shape[1] == 1:
            counts, edges = np.histogram(x, bins=16, range=support)
            coord = (edges[:-1] + edges[1:]) / 2
            if tag == "density_radial":
                coord = np.abs(coord - sum(support) / 2)
        else:
            counts, edges, _ = np.histogram2d(
                p[:, 0], p[:, 1], bins=16, range=[support, support]
            )
            centers = (edges[:-1] + edges[1:]) / 2
            xx, yy = np.meshgrid(centers, centers, indexing="ij")
            coord = (
                np.hypot(xx, yy)
                if tag == "density_radial"
                else (xx if axis == 0 else yy)
            )
        a, b = counts.ravel(), coord.ravel()
        return 0.0 if np.ptp(a) == 0 else float(abs(spearmanr(a, b).statistic))
    counts, _ = np.histogram(x, bins=128, range=support)
    if counts.sum() == 0:
        raise ValueError("coordinates outside support")
    if tag.startswith("modality"):
        # Binned Gaussian KDE, bandwidth 6/128 of fixed support; prominence 10%.
        smooth = gaussian_filter1d(counts.astype(float), 6, mode="constant")
        peaks, _ = find_peaks(
            np.r_[0, smooth, 0], prominence=0.1 * smooth.max(), distance=12
        )
        return float(len(peaks))
    # Joint reflection for point clouds, not merely symmetry of a marginal.
    if p.shape[1] == 2:
        counts, _, _ = np.histogram2d(
            p[:, 0], p[:, 1], bins=32, range=[support, support]
        )
    reflected = np.flip(counts, axis=axis if p.shape[1] == 2 else 0)
    return float(1 - np.abs(counts - reflected).sum() / (2 * counts.sum()))


def two(a, b, tag, support):
    if tag == "spacing_ks":
        r = ks_2samp(checked(a)[:, 0], checked(b)[:, 0], method="asymp")
        # More large spacings = smaller CDF at the maximal absolute difference.
        return float(
            r.statistic
        ), "A" if r.statistic_sign < 0 else "B" if r.statistic > 0 else None
    delta = value(a, tag, support) - value(b, tag, support)
    return abs(delta), "A" if delta > 0 else "B" if delta < 0 else None


def alternative(points, tag, support):
    """Pinned sensitivity alternatives, not fitted to observed development outcomes."""
    p = checked(points).copy()
    n = len(p)
    axis = 1 if tag.endswith("_y") else 0
    lo, hi = support
    mid = (lo + hi) / 2
    width = hi - lo
    if tag.startswith("modality"):
        p[:, axis] = (
            mid
            + np.where(np.arange(n) % 2, 1, -1) * width * 0.28
            + np.sin(np.arange(n)) * width * 0.018
        )
    elif tag.startswith("reflection"):
        half = p[: n // 2].copy()
        reflected = half.copy()
        reflected[:, axis] = 2 * mid - half[:, axis]
        p = np.resize(np.concatenate((half, reflected)), p.shape)
    elif tag == "density_radial":
        p *= 0.25
    elif tag.startswith("density"):
        p[:, axis] = lo + width * (np.arange(n) / (n - 1)) ** 4
    else:
        p[:, 0] *= 1.7
    return p
