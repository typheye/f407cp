"""Geometry-constrained feeder tape detector.

The carrier tape is identified by two independent structures: circular
sprocket holes and rectangular pockets.  Their spacing is deliberately not
used as a calibration constant; only collinearity and parallel orientation
are used to reject reflections and unrelated components.
"""
import math
import time
from collections import deque
import cv2
import numpy as np


_TARGET_HISTORY = deque(maxlen=5)
_TARGET_HISTORY_TIME = 0.0
_PENDING_TARGET = None
_PENDING_COUNT = 0


def _stabilize_target(x, y):
    global _TARGET_HISTORY_TIME, _PENDING_TARGET, _PENDING_COUNT
    now = time.monotonic()
    if now - _TARGET_HISTORY_TIME > 0.6:
        _TARGET_HISTORY.clear()
        _PENDING_TARGET = None
        _PENDING_COUNT = 0
    if _TARGET_HISTORY:
        mx = float(np.median([p[0] for p in _TARGET_HISTORY]))
        my = float(np.median([p[1] for p in _TARGET_HISTORY]))
        if math.hypot(float(x) - mx, float(y) - my) > 12.0:
            if _PENDING_TARGET and math.hypot(float(x) - _PENDING_TARGET[0], float(y) - _PENDING_TARGET[1]) <= 5.0:
                _PENDING_COUNT += 1
            else:
                _PENDING_TARGET = (float(x), float(y))
                _PENDING_COUNT = 1
            if _PENDING_COUNT < 2:
                return mx, my
            _TARGET_HISTORY.clear()
        else:
            _PENDING_TARGET = None
            _PENDING_COUNT = 0
    _TARGET_HISTORY.append((float(x), float(y)))
    _TARGET_HISTORY_TIME = now
    return (float(np.median([p[0] for p in _TARGET_HISTORY])),
            float(np.median([p[1] for p in _TARGET_HISTORY])))


def _center(c):
    m = cv2.moments(c)
    if abs(m.get("m00", 0.0)) < 1e-9:
        x, y, w, h = cv2.boundingRect(c)
        return float(x + w / 2), float(y + h / 2)
    return float(m["m10"] / m["m00"]), float(m["m01"] / m["m00"])


def _roi(img, config):
    h, w = img.shape[:2]
    r = config.get("roi") if isinstance(config, dict) else None
    if not r:
        # Match the feeder ROI used by BasicVIN on the calibrated 640x480
        # Camera 1 frame.  JAPKit often has no explicit ROI selected, so a
        # proportional default keeps its debug input identical to production.
        r = (w * 253.0 / 640.0, h * 114.0 / 480.0,
             w * 86.0 / 640.0, h * 234.0 / 480.0)
    if isinstance(r, dict):
        r = (r.get("x", 0), r.get("y", 0), r.get("width", 0), r.get("height", 0))
    x, y, rw, rh = [int(round(float(v))) for v in r]
    if config.get("structured_expand_roi", True):
        x -= int(round(rw * 0.6)); y -= int(round(rh * 0.1))
        rw = int(round(rw * 2.2)); rh = int(round(rh * 1.2))
    x = max(0, min(w - 1, x)); y = max(0, min(h - 1, y))
    rw = max(1, min(w - x, rw)); rh = max(1, min(h - y, rh))
    return img[y:y + rh, x:x + rw], x, y


def detect_feeder_structured(img, config=None):
    """Return a BasicVIN-compatible result, or None when geometry is ambiguous."""
    if img is None:
        return None
    config = config or {}
    debug = bool(config.get("structured_debug", False))
    roi, ox, oy = _roi(img, config)
    h, w = roi.shape[:2]
    if h < 30 or w < 30:
        return None
    raw_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    # Divide out slow illumination changes before local thresholding. This
    # retains pocket and sprocket edges when the ring light creates a broad
    # white reflection across the beige carrier tape.
    illumination = cv2.GaussianBlur(raw_gray, (0, 0), sigmaX=17.0, sigmaY=17.0)
    normalized = cv2.divide(
        raw_gray, np.maximum(illumination, 1), scale=128.0
    )
    normalized = cv2.createCLAHE(
        clipLimit=1.8, tileGridSize=(8, 8)
    ).apply(normalized)
    raw_equalized = cv2.createCLAHE(
        clipLimit=1.5, tileGridSize=(8, 8)
    ).apply(raw_gray)
    blur = cv2.GaussianBlur(normalized, (5, 5), 0)

    # Circular sprocket holes: use Hough plus a contour fallback for tiny holes.
    min_r = max(2, int(round(min(h, w) * 0.012)))
    max_r = max(min_r + 2, int(round(min(h, w) * 0.075)))
    circles = cv2.HoughCircles(blur, cv2.HOUGH_GRADIENT, dp=1.2,
                               minDist=max(5, min_r * 2), param1=70,
                               param2=11, minRadius=min_r, maxRadius=max_r)
    holes = []
    if circles is not None:
        for x, y, r in np.round(circles[0]).astype(int):
            if not (4 <= x < w - 4 and 4 <= y < h - 4):
                continue
            radius = max(3, int(r))
            x1, x2 = max(0, x - radius * 2), min(w, x + radius * 2 + 1)
            y1, y2 = max(0, y - radius * 2), min(h, y + radius * 2 + 1)
            patch = blur[y1:y2, x1:x2]
            yy, xx = np.ogrid[:patch.shape[0], :patch.shape[1]]
            radial = np.sqrt((xx - (x - x1)) ** 2 + (yy - (y - y1)) ** 2)
            inner = patch[radial <= radius * 0.65]
            ring = patch[(radial >= radius * 1.2) & (radial <= radius * 1.8)]
            if inner.size == 0 or ring.size == 0 or float(np.mean(ring) - np.mean(inner)) < 15.0:
                continue
            _, local = cv2.threshold(patch, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            local_contours, _ = cv2.findContours(local, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not local_contours:
                continue
            pcx, pcy = float(x - x1), float(y - y1)
            containing = [
                (cv2.pointPolygonTest(c, (pcx, pcy), True), c)
                for c in local_contours
                if cv2.pointPolygonTest(c, (pcx, pcy), True) >= 0
            ]
            contour = (
                max(containing, key=lambda item: item[0])[1]
                if containing
                else min(
                    local_contours,
                    key=lambda c: abs(
                        cv2.pointPolygonTest(c, (pcx, pcy), True)
                    ),
                )
            )
            area = float(cv2.contourArea(contour)); perimeter = float(cv2.arcLength(contour, True))
            circularity = 4.0 * math.pi * area / max(1.0, perimeter * perimeter)
            # Rectangular component pockets can also trigger Hough under a
            # strong highlight. Their contour circularity is typically below
            # 0.79, while real sprocket holes remain above it.
            if circularity >= 0.79:
                holes.append((float(x), float(y), float(r)))

    # Dark rectangular pockets/components.  Adaptive threshold handles beige
    # tape and changing illumination while morphology retains small packages.
    dark_normalized = cv2.adaptiveThreshold(
        blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 31, 5,
    )
    raw_blur = cv2.GaussianBlur(raw_equalized, (5, 5), 0)
    dark_raw = cv2.adaptiveThreshold(
        raw_blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 31, 5,
    )
    # A black-hat response recovers dark pocket borders next to saturated
    # highlights without turning the bright highlight itself into a pocket.
    blackhat = cv2.morphologyEx(
        normalized,
        cv2.MORPH_BLACKHAT,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)),
    )
    _, dark_blackhat = cv2.threshold(
        blackhat, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )
    dark = cv2.bitwise_or(dark_normalized, dark_raw)
    dark = cv2.bitwise_or(dark, dark_blackhat)
    dark = cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    dark = cv2.morphologyEx(
        dark, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8)
    )
    contours, _ = cv2.findContours(dark, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    if debug:
        contour_stats = []
        for contour in contours:
            area = float(cv2.contourArea(contour))
            rw, rh = cv2.minAreaRect(contour)[1]
            if area >= 4:
                contour_stats.append(
                    (round(area, 1), round(float(rw), 1), round(float(rh), 1))
                )
        print(
            f"[FeederStructured] contour_stats="
            f"{sorted(contour_stats, reverse=True)[:24]}"
        )

    # The sprocket-hole contours are more stable than Hough on occasional
    # exposure-transition frames.  Their area/circularity range is distinct
    # from the much smaller component and reflection contours at 100% light.
    for c in contours:
        area = float(cv2.contourArea(c))
        perimeter = float(cv2.arcLength(c, True))
        x, y, cw, ch = cv2.boundingRect(c)
        aspect = min(cw, ch) / max(1.0, max(cw, ch))
        circularity = 4.0 * math.pi * area / max(1.0, perimeter * perimeter)
        if not (200.0 <= area <= 900.0 and aspect >= 0.78 and circularity >= 0.80):
            continue
        cx, cy = _center(c)
        radius = (float(cw) + float(ch)) * 0.25
        if not any(math.hypot(cx - hx, cy - hy) <= max(radius, hr) * 0.7 for hx, hy, hr in holes):
            holes.append((cx, cy, radius))

    pockets = []
    for c in contours:
        area = float(cv2.contourArea(c))
        if area < 5 or area > max(2500, w * h * 0.08):
            continue
        rect = cv2.minAreaRect(c)
        rw, rh = rect[1]
        if min(rw, rh) < 4 or max(rw, rh) / max(1.0, min(rw, rh)) > 3.0:
            continue
        fill = area / max(1.0, rw * rh)
        if fill < 0.12:
            continue
        cx, cy = _center(c)
        pockets.append((cx, cy, rw, rh, area, rect[2]))

    if len(holes) < 3 or len(pockets) < 2:
        if debug:
            print(
                f"[FeederStructured] insufficient geometry "
                f"holes={len(holes)} pockets={len(pockets)}"
            )
        return None

    def select_hole_line(candidates):
        best = None
        median_r = float(np.median([p[2] for p in candidates]))
        tolerance = max(3.0, median_r * 0.45)
        for i, first in enumerate(candidates):
            for second in candidates[i + 1:]:
                vector = np.asarray((second[0] - first[0], second[1] - first[1]), dtype=float)
                length = float(np.linalg.norm(vector))
                if length < median_r * 3.0:
                    continue
                direction = vector / length
                normal = np.asarray((-direction[1], direction[0]))
                group = [p for p in candidates if abs(float(np.dot((p[0] - first[0], p[1] - first[1]), normal))) <= tolerance]
                if len(group) < 3:
                    continue
                along = [float(np.dot((p[0] - first[0], p[1] - first[1]), direction)) for p in group]
                span = max(along) - min(along)
                radii = [p[2] for p in group]
                radius_cv = float(np.std(radii) / max(1.0, np.mean(radii)))
                ordered = sorted(along)
                gaps = np.diff(ordered)
                gap_cv = float(np.std(gaps) / max(1.0, np.mean(gaps))) if len(gaps) >= 2 else 1.0
                if radius_cv > 0.28 or gap_cv > 0.35:
                    continue
                score = (len(group), -gap_cv, -radius_cv, span)
                if best is None or score > best[0]:
                    best = (score, group)
        return best[1] if best is not None else []

    holes = select_hole_line(holes)
    if len(holes) < 3:
        if debug:
            print("[FeederStructured] no consistent sprocket-hole line")
        return None
    # Exclude overlaps only after choosing the physical sprocket line. Hough
    # false circles on rectangular pockets must not erase those pockets.
    pockets = [
        p for p in pockets
        if not any(
            math.hypot(p[0] - hx, p[1] - hy) < hr * 1.4
            for hx, hy, hr in holes
        )
    ]
    if len(pockets) < 2:
        if debug:
            print("[FeederStructured] pockets overlap selected hole line")
        return None

    # Fit the dominant hole axis and pocket axis independently.  The axes must
    # be parallel (within 12 degrees), but have no required separation.
    def axis(points):
        pts = np.asarray(points, dtype=np.float32)
        mean, vec, _ = cv2.PCACompute2(pts, mean=None)
        v = vec[0]; angle = math.degrees(math.atan2(float(v[1]), float(v[0])))
        return mean[0], angle

    hole_mean, hole_angle = axis([(x, y) for x, y, _ in holes])
    # Prefer a pocket line with at least two members; otherwise use all pockets.
    theta = math.radians(hole_angle)
    direction = np.asarray((math.cos(theta), math.sin(theta)), dtype=float)
    normal = np.asarray((-direction[1], direction[0]), dtype=float)
    hole_cross = float(np.dot(hole_mean, normal))
    median_radius = float(np.median([r for _, _, r in holes]))
    optical_x = img.shape[1] / 2.0 - ox
    optical_y = img.shape[0] / 2.0 - oy
    tolerance = max(4.0, median_radius * 0.8)
    groups = []
    for source in (pockets,):
        usable = [p for p in source if abs(float(np.dot((p[0], p[1]), normal)) - hole_cross) > max(7.0, median_radius * 2.2)]
        for seed in usable:
            seed_cross = float(np.dot((seed[0], seed[1]), normal))
            group = [p for p in usable if abs(float(np.dot((p[0], p[1]), normal)) - seed_cross) <= tolerance]
            along = [float(np.dot((p[0], p[1]), direction)) for p in group]
            if len(group) >= 2 and max(along) - min(along) > max(8.0, median_radius * 2.0):
                groups.append(group)
        if groups:
            break
    if not groups:
        if debug:
            print(
                f"[FeederStructured] no parallel pocket line "
                f"holes={len(holes)} pockets={len(pockets)}"
            )
        return None
    groups.sort(key=lambda g: (min(math.hypot(p[0] - optical_x, p[1] - optical_y) for p in g), -len(g)))
    pocket_line = groups[0]
    pocket_mean = np.mean(np.asarray([(p[0], p[1]) for p in pocket_line], dtype=float), axis=0)
    pocket_angle = hole_angle

    cx0, cy0 = optical_x, optical_y
    # Score small, well-formed pockets near image center.  A nearby hole axis
    # is required, but its distance is not constrained.
    best = None
    for p in pocket_line:
        cx, cy, rw, rh, area, ang = p
        dist = math.hypot(cx - cx0, cy - cy0)
        axis_dist = abs((cx - hole_mean[0]) * math.sin(math.radians(hole_angle))
                        - (cy - hole_mean[1]) * math.cos(math.radians(hole_angle)))
        score = dist + axis_dist * 2.0 + max(0.0, 10.0 - min(rw, rh)) * 0.5
        if best is None or score < best[0]:
            best = (score, p)
    if best is None or best[1][4] < 5:
        return None
    _, (px, py, rw, rh, area, ang) = best
    selected_along = float(np.dot((px, py), direction))
    same_row = [p for p in pocket_line if abs(float(np.dot((p[0], p[1]), direction)) - selected_along) <= max(5.0, median_radius * 1.5)]
    pocket_theta = math.radians(pocket_angle)
    pocket_direction = np.asarray((math.cos(pocket_theta), math.sin(pocket_theta)), dtype=float)
    pocket_normal = np.asarray((-pocket_direction[1], pocket_direction[0]), dtype=float)
    row_source = same_row or [best[1]]
    row_along = float(np.median([np.dot((p[0], p[1]), pocket_direction) for p in row_source]))
    pocket_cross = float(np.median([np.dot((p[0], p[1]), pocket_normal) for p in pocket_line]))
    px, py = (pocket_direction * row_along + pocket_normal * pocket_cross).tolist()
    px, py = _stabilize_target(px + ox, py + oy)
    center_x, center_y = img.shape[1] / 2.0, img.shape[0] / 2.0
    tx, ty = px, py
    poly = cv2.boxPoints(((px, py), (rw, rh), ang)).astype(int)
    return {
        "found": True, "target_type": "feeder", "center_x": int(round(center_x)),
        "center_y": int(round(center_y)), "target_x": int(round(tx)),
        "target_y": int(round(ty)), "offset_x": int(round(tx - center_x)),
        "offset_y": int(round(ty - center_y)), "rect_x": int(round(tx - rw / 2)),
        "rect_y": int(round(ty - rh / 2)), "rect_width": int(round(rw)),
        "rect_height": int(round(rh)), "detected_pixels": int(cv2.countNonZero(dark)),
        "total_pixels": int(w * h), "coverage_percent": round(100.0 * cv2.countNonZero(dark) / max(1, w * h), 2),
        "feeder_holes": [{"x": int(round(x + ox)), "y": int(round(y + oy)), "r": int(round(r))} for x, y, r in holes],
        "feeder_pocket": [{"x": int(x), "y": int(y)} for x, y in poly],
        "feeder_roi": {"x": int(ox), "y": int(oy), "width": int(w), "height": int(h)},
        "feeder_axis_angle": round(float(hole_angle), 2),
    }


def draw_feeder_debug(img, result):
    """Draw diagnostics without changing the copied Host detector result."""
    out = img.copy()
    if not result:
        cv2.putText(
            out, "FEEDER: ambiguous", (12, 28), cv2.FONT_HERSHEY_SIMPLEX,
            0.7, (0, 0, 255), 2,
        )
        return out
    for hole in result.get("feeder_holes", []):
        cv2.circle(
            out, (hole["x"], hole["y"]), hole["r"], (0, 220, 255), 2
        )
    points = np.asarray(
        [[point["x"], point["y"]] for point in result.get("feeder_pocket", [])],
        np.int32,
    )
    if len(points) >= 3:
        cv2.polylines(out, [points], True, (0, 255, 0), 2)
    cv2.drawMarker(
        out,
        (result["target_x"], result["target_y"]),
        (0, 255, 0),
        cv2.MARKER_CROSS,
        22,
        2,
    )
    cv2.putText(
        out, "FEEDER: joint geometry", (12, 28), cv2.FONT_HERSHEY_SIMPLEX,
        0.7, (0, 255, 0), 2,
    )
    return out
