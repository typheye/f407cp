"""HSV target, PCB silhouette, and board-corner detection algorithms."""

import math
import time

import cv2
import numpy as np

try:
    from .feeder_structured import detect_feeder_structured
except ImportError:
    from feeder_structured import detect_feeder_structured

try:
    from .component_check import _component_check_detector
except ImportError:
    from component_check import _component_check_detector

# ==================== HSV/Geometry Helper Functions ====================
def _safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def _clamp_roi(img_shape, roi):
    h, w = img_shape[:2]
    if not roi:
        return 0, 0, w, h

    x = _safe_int(roi.get("x", 0), 0)
    y = _safe_int(roi.get("y", 0), 0)
    roi_w = _safe_int(roi.get("width", w), w)
    roi_h = _safe_int(roi.get("height", h), h)

    x = max(0, min(x, w))
    y = max(0, min(y, h))
    roi_w = max(0, min(roi_w, w - x))
    roi_h = max(0, min(roi_h, h - y))

    if roi_w <= 0 or roi_h <= 0:
        return 0, 0, w, h
    return x, y, roi_w, roi_h


def _build_hsv_mask(img, config, ignore_invert=False, custom_thresholds=None):
    """Generate full-image-size HSV mask according to config, and return ROI statistics."""
    h, w = img.shape[:2]
    x, y, roi_w, roi_h = _clamp_roi(img.shape, config.get("roi"))
    roi_img = img[y : y + roi_h, x : x + roi_w]

    hsv_img = cv2.cvtColor(roi_img, cv2.COLOR_BGR2HSV)
    S = hsv_img[:, :, 1]
    V = hsv_img[:, :, 2]

    hsv_thresholds = dict(config.get("hsv_thresholds", {}))
    if custom_thresholds:
        hsv_thresholds.update(custom_thresholds)

    S_min = _safe_int(hsv_thresholds.get("S_min", 0), 0)
    S_max = _safe_int(hsv_thresholds.get("S_max", 255), 255)
    V_min = _safe_int(hsv_thresholds.get("V_min", 0), 0)
    V_max = _safe_int(hsv_thresholds.get("V_max", 255), 255)
    invert = bool(hsv_thresholds.get("invert", False))

    mask_roi = (S >= S_min) & (S <= S_max) & (V >= V_min) & (V <= V_max)
    if invert and not ignore_invert:
        mask_roi = ~mask_roi

    mask_uint8_roi = (mask_roi.astype(np.uint8)) * 255
    full_mask = np.zeros((h, w), dtype=np.uint8)
    full_mask[y : y + roi_h, x : x + roi_w] = mask_uint8_roi

    total_pixels = int(roi_w * roi_h)
    detected_pixels = int(np.count_nonzero(mask_uint8_roi))
    coverage = (detected_pixels / total_pixels * 100.0) if total_pixels > 0 else 0.0
    return full_mask, detected_pixels, total_pixels, coverage, (x, y, roi_w, roi_h)


def _fill_holes(mask_uint8):
    """Fill holes inside the mask to prevent cutouts/black silkscreen on the board from fragmenting rectangular regions."""
    if mask_uint8 is None or mask_uint8.size == 0:
        return mask_uint8

    mask = mask_uint8.copy()
    h, w = mask.shape[:2]
    flood = mask.copy()
    flood_mask = np.zeros((h + 2, w + 2), dtype=np.uint8)

    # Try flood fill from four corners; even if a corner happens to be the target area, it won't affect subsequent largest contour detection.
    for seed in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        try:
            if flood[seed[1], seed[0]] == 0:
                cv2.floodFill(flood, flood_mask, seed, 255)
        except Exception:
            pass

    flood_inv = cv2.bitwise_not(flood)
    return cv2.bitwise_or(mask, flood_inv)


def _odd_kernel_size(value, min_value=3, max_value=99):
    """Normalize any value to an odd kernel size usable by OpenCV."""
    k = _safe_int(value, min_value)
    k = max(min_value, min(k, max_value))
    if k % 2 == 0:
        k += 1
    return max(min_value, min(k, max_value if max_value % 2 == 1 else max_value - 1))


def _auto_board_body_kernel(config, roi_box):
    """Large closing kernel for PCB body repair.

    This kernel is not for finding details, but to swallow screw holes, cutouts, silkscreen text,
    and dark pad areas on the board, so that subsequent geometry only deals with the PCB outer contour.
    """
    if roi_box:
        _, _, roi_w, roi_h = roi_box
        short_side = max(1, min(int(roi_w), int(roi_h)))
    else:
        short_side = 260

    ratio = _safe_float(config.get("board_body_close_ratio", 0.12), 0.12)
    auto_k = int(round(short_side * ratio))
    fixed_k = config.get("board_body_close_kernel", None)
    if fixed_k is not None:
        auto_k = max(auto_k, _safe_int(fixed_k, auto_k))

    max_k = _safe_int(config.get("board_body_close_kernel_max", 81), 81)
    max_k = max(17, min(max_k, 121))
    return _odd_kernel_size(auto_k, min_value=9, max_value=max_k)


def _preprocess_board_mask(mask_uint8, config, roi_box=None):
    """Morphological processing specialized for board edges.

    Key point: PCB vertex detection cannot directly trust small local contours, otherwise screw hole rings, silkscreen,
    and cutout areas would be treated as "corners" by minAreaRect. This is done in two steps:
    1) Small closing: compatible with the original threshold config;
    2) Large closing + hole filling: rebuild PCB body outer contour, intentionally swallowing screw holes/silkscreen.
    """
    if mask_uint8 is None:


        return mask_uint8

    k = _safe_int(config.get("board_close_kernel", config.get("morph_kernel", 7)), 7)
    k = _odd_kernel_size(k, min_value=3, max_value=31)

    close_iter = _safe_int(config.get("board_close_iterations", 2), 2)
    close_iter = max(1, min(close_iter, 5))

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))
    processed = cv2.morphologyEx(
        mask_uint8, cv2.MORPH_CLOSE, kernel, iterations=close_iter
    )
    processed = _fill_holes(processed)

    # PCB body repair: enabled by default. It swallows screw holes, silkscreen, and cutouts,
    # avoiding treating these internal structures as PCB outer edge vertices.
    if bool(config.get("board_enable_body_heal", True)):
        body_k = _auto_board_body_kernel(config, roi_box)
        body_iter = _safe_int(config.get("board_body_close_iterations", 1), 1)
        body_iter = max(1, min(body_iter, 3))
        body_kernel_shape = str(
            config.get("board_body_kernel_shape", "ellipse")
        ).lower()
        if body_kernel_shape == "rect":
            body_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (body_k, body_k))
        else:
            body_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (body_k, body_k))
        processed = cv2.morphologyEx(
            processed, cv2.MORPH_CLOSE, body_kernel, iterations=body_iter
        )
        processed = _fill_holes(processed)

    open_k = _safe_int(config.get("board_open_kernel", 3), 3)
    if open_k > 1:
        open_k = _odd_kernel_size(open_k, min_value=3, max_value=21)
        open_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (open_k, open_k))
        processed = cv2.morphologyEx(
            processed, cv2.MORPH_OPEN, open_kernel, iterations=1
        )

    return processed


def _contour_center(contour):
    M = cv2.moments(contour)
    if M["m00"] != 0:
        return float(M["m10"] / M["m00"]), float(M["m01"] / M["m00"])
    x, y, w, h = cv2.boundingRect(contour)
    return float(x + w / 2), float(y + h / 2)


def _quantize_center_offset(value, deadband_px=1.5):
    value = float(value)
    if abs(value) <= float(deadband_px):
        return 0
    return int(round(value))


def _angle_deg(p1, p2):
    return math.degrees(math.atan2(float(p2[1] - p1[1]), float(p2[0] - p1[0])))


def _normalize_line_angle(angle):
    """Normalize line angle to [-90, 90] for representing horizontal edge deflection."""
    while angle <= -90.0:
        angle += 180.0
    while angle > 90.0:
        angle -= 180.0
    return angle


def _point_distance(p1, p2):
    return float(((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** 0.5)


def _get_board_roi_guard_margin(config, roi_box):
    """Calculate inner edge guard margin width within the board ROI, to avoid treating ROI crop edges as PCB edges.

    Default: max(board_roi_guard_margin_px, min(roi_w, roi_h) * board_roi_guard_ratio).
    Can be overridden in board_result.json:
      - board_roi_guard_margin_px: fixed pixel guard width, default 18
      - board_roi_guard_ratio: ratio of ROI short side, default 0.06
      - board_roi_guard_max_px: max guard width, default 48
    """
    _, _, roi_w, roi_h = roi_box
    px = _safe_float(config.get("board_roi_guard_margin_px", 18), 18)
    ratio = _safe_float(config.get("board_roi_guard_ratio", 0.06), 0.06)
    max_px = _safe_float(config.get("board_roi_guard_max_px", 48), 48)
    guard = max(px, float(min(roi_w, roi_h)) * ratio)
    guard = max(0.0, min(guard, max_px, float(max(0, min(roi_w, roi_h) // 2 - 1))))
    return float(guard)


def _point_roi_edge_distance(point, roi_box):
    """Minimum distance from a point to the four edges of the ROI."""
    px, py = float(point[0]), float(point[1])
    x, y, roi_w, roi_h = roi_box
    left = abs(px - x)
    top = abs(py - y)
    right = abs((x + roi_w - 1) - px)
    bottom = abs((y + roi_h - 1) - py)
    return float(min(left, top, right, bottom))


def _is_point_in_roi_guard(point, roi_box, guard_px):
    """Check whether a point falls within the ROI inner edge guard zone.

    Note: this is an "inner padding" filter. If a corner point is too close to any ROI edge,
    it is considered to possibly come from the ROI crop boundary rather than the real PCB edge.
    """
    if guard_px <= 0:
        return False
    px, py = float(point[0]), float(point[1])
    x, y, roi_w, roi_h = roi_box
    return (
        px <= x + guard_px
        or py <= y + guard_px
        or px >= x + roi_w - 1 - guard_px
        or py >= y + roi_h - 1 - guard_px
    )


def _detect_dark_circles_in_roi(img, roi_box, config):
    """Detect obvious dark circular structures (screw holes/rings) within the ROI, for suppressing false detections."""
    if img is None or roi_box is None:
        return []
    if not bool(config.get("board_enable_circle_guard", True)):
        return []

    x, y, roi_w, roi_h = roi_box
    if roi_w < 20 or roi_h < 20:
        return []

    roi = img[y : y + roi_h, x : x + roi_w]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (9, 9), 1.5)

    roi_short = max(1, min(roi_w, roi_h))
    dp = max(1.0, _safe_float(config.get("board_circle_dp", 1.2), 1.2))
    min_dist = int(
        max(
            10,
            roi_short
            * _safe_float(config.get("board_circle_min_dist_ratio", 0.10), 0.10),
        )
    )
    param1 = _safe_int(config.get("board_circle_param1", 90), 90)
    param2 = _safe_int(config.get("board_circle_param2", 18), 18)
    min_radius = int(
        max(

            5,
            roi_short
            * _safe_float(config.get("board_circle_min_radius_ratio", 0.04), 0.04),
        )
    )
    max_radius = int(
        max(
            min_radius + 2,
            roi_short
            * _safe_float(config.get("board_circle_max_radius_ratio", 0.18), 0.18),
        )
    )

    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=dp,
        minDist=min_dist,
        param1=param1,
        param2=param2,
        minRadius=min_radius,
        maxRadius=max_radius,
    )

    out = []
    if circles is not None and len(circles) > 0:
        for cx, cy, r in np.round(circles[0, :]).astype(int):
            # Filter out false circles too close to ROI edges, avoiding treating ROI crop arc edges as screw holes
            edge_margin = _safe_int(config.get("board_circle_edge_margin_px", 12), 12)
            if (
                cx - r <= edge_margin
                or cy - r <= edge_margin
                or cx + r >= roi_w - edge_margin
                or cy + r >= roi_h - edge_margin
            ):
                continue
            out.append((int(cx + x), int(cy + y), int(r)))
    return out


def _point_near_any_circle(point, circles, config):
    """Check whether a corner point is near a circular structure, for excluding screw hole edges."""
    if not circles:
        return False, None
    expand = float(_safe_float(config.get("board_circle_expand_px", 8), 8))
    band = float(_safe_float(config.get("board_circle_reject_corner_band_px", 10), 10))
    px, py = float(point[0]), float(point[1])
    for cx, cy, r in circles:
        d = ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5
        # Close to the circumference, or directly inside the enlarged circle area, both are considered suspicious
        if abs(d - float(r)) <= band or d <= float(r) + expand:
            return True, {
                "cx": int(cx),
                "cy": int(cy),
                "r": int(r),
                "distance": round(float(d), 2),
            }
    return False, None


def _count_box_points_in_roi_guard(points, roi_box, guard_px):
    if points is None:
        return 0
    return sum(1 for p in points if _is_point_in_roi_guard(p, roi_box, guard_px))


def _order_box_points(box):
    """Return order: LT, RT, RB, LB."""
    pts = np.array(box, dtype=np.float32)
    rect = np.zeros((4, 2), dtype=np.float32)

    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]  # left-top
    rect[2] = pts[np.argmax(s)]  # right-bottom

    diff = pts[:, 1] - pts[:, 0]
    rect[1] = pts[np.argmin(diff)]  # right-top
    rect[3] = pts[np.argmax(diff)]  # left-bottom
    return rect


def _select_corner_index(corners, center_x, center_y, config):
    mode = str(
        config.get("board_corner_mode", config.get("corner_mode", "closest_to_center"))
    ).lower()
    mapping = {
        "lt": 0,
        "tl": 0,
        "left_top": 0,
        "top_left": 0,
        "rt": 1,
        "tr": 1,
        "right_top": 1,
        "top_right": 1,
        "rb": 2,
        "br": 2,
        "rd": 2,
        "right_bottom": 2,
        "bottom_right": 2,
        "lb": 3,
        "bl": 3,
        "ld": 3,
        "left_bottom": 3,
        "bottom_left": 3,
    }
    if mode in mapping:
        return mapping[mode], mode

    center = np.array([center_x, center_y], dtype=np.float32)
    dists = [float(np.linalg.norm(corners[i] - center)) for i in range(4)]
    return int(np.argmin(dists)), "closest_to_center"


def _make_empty_result(
    target_name,
    img_shape=None,
    detected_pixels=0,
    total_pixels=0,
    coverage=0.0,
    message="",
):
    if img_shape is None:
        center_x, center_y = 0, 0
    else:
        h, w = img_shape[:2]
        center_x, center_y = w // 2, h // 2

    result = {
        "found": False,
        "target_type": target_name,
        "center_x": int(center_x),
        "center_y": int(center_y),
        "target_x": 0,
        "target_y": 0,
        "offset_x": 0,
        "offset_y": 0,
        "rect_x": 0,
        "rect_y": 0,
        "rect_width": 0,
        "rect_height": 0,
        "detected_pixels": int(detected_pixels),
        "total_pixels": int(total_pixels),
        "coverage_percent": round(float(coverage), 2),
        "timestamp": time.time(),
    }

    if message:
        result["message"] = message

    if target_name in ("board", "board_scan"):

        result.update(
            {
                "board_found": False,
                "board_center_x": 0,
                "board_center_y": 0,
                "board_corner_x": 0,
                "board_corner_y": 0,
                "board_corner_index": -1,
                "board_corner_mode": "",
                "board_corners": [],
                "board_edges": [],
                "board_angle_deg": 0.0,
                "board_long_edge_angle_deg": 0.0,
                "board_contour_area": 0.0,
                "board_rect_area": 0.0,
                "board_mask_method": "",
                "board_contour": [],
                "board_roi_guard_margin_px": 0.0,
                "board_corner_roi_edge_distance_px": 0.0,
                "board_box_guard_corner_count": 0,
                "board_bbox_coverage_percent": 0.0,
                "board_detected_circles": [],
                "board_corner_near_circle": False,
                "board_corner_near_circle_info": None,
            }
        )
    elif target_name == "check":
        result.update({"reserved": True, "implemented": False})

    return result


# ==================== Detector ====================
class HSVTargetDetector:
    """HSV threshold-based target detector. Feeder uses the original logic, board uses edge/rectangle-specific logic."""

    def __init__(self, config, target_name="feeder", camera_id=1):
        self.config = config or {}
        self.target_name = target_name
        self.camera_id = int(camera_id)
        self.roi = self.config.get("roi")
        self.hsv_thresholds = self.config.get("hsv_thresholds", {})
        self.invert = self.hsv_thresholds.get("invert", False)

    def detect(self, img):
        if self.target_name == "board_scan":
            return self.detect_board_scan(img)
        if self.target_name == "board":
            return self.detect_board(img)
        if self.target_name == "check":
            return self.detect_check(img)
        if self.target_name == "feeder":
            result = detect_feeder_structured(img, self.config)
            if result is not None:
                result["timestamp"] = time.time()
                return result
            return _make_empty_result(
                "feeder", img.shape if img is not None else None,
                message="Feeder tape geometry is missing or ambiguous",
            )
        return self.detect_standard(img)

    def detect_board_scan(self, img):
        """Return the visible PCB silhouette without imposing a corner or shape."""
        if img is None or self.config is None:
            return _make_empty_result("board_scan")

        h, w = img.shape[:2]
        center_x, center_y = w // 2, h // 2
        scan_config = dict(self.config)
        scan_config["roi"] = None
        original_config = self.config
        self.config = scan_config
        best = None
        try:
            for method, raw_mask, _, _, _, roi_box in self._board_mask_candidates(img):
                processed = _preprocess_board_mask(raw_mask, scan_config, roi_box)
                contours, _ = cv2.findContours(
                    processed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                )
                frame_area = float(max(1, w * h))
                for contour in contours:
                    area = float(cv2.contourArea(contour))
                    if area < max(220.0, frame_area * 0.002):
                        continue
                    if area > frame_area * 0.92:
                        continue
                    if best is None or area > best[0]:
                        best = (area, method, contour)
        finally:
            self.config = original_config

        if best is None:
            return _make_empty_result(
                "board_scan", img.shape, message="No PCB silhouette in scan frame"
            )

        area, method, contour = best
        perimeter = max(1.0, float(cv2.arcLength(contour, True)))
        polygon = cv2.approxPolyDP(contour, perimeter * 0.008, True).reshape(-1, 2)
        if len(polygon) > 64:
            stride = int(math.ceil(len(polygon) / 64.0))
            polygon = polygon[::stride]
        cx, cy = _contour_center(contour)
        x, y, rect_w, rect_h = cv2.boundingRect(contour)
        return {
            "found": True,
            "target_type": "board_scan",
            "center_x": int(center_x),
            "center_y": int(center_y),
            "target_x": int(round(cx)),
            "target_y": int(round(cy)),
            "offset_x": _quantize_center_offset(cx - center_x),
            "offset_y": _quantize_center_offset(cy - center_y),
            "rect_x": int(x),
            "rect_y": int(y),
            "rect_width": int(rect_w),
            "rect_height": int(rect_h),
            "detected_pixels": int(round(area)),
            "total_pixels": int(w * h),
            "coverage_percent": round(area / float(max(1, w * h)) * 100.0, 2),
            "board_center_x": int(round(cx)),
            "board_center_y": int(round(cy)),
            "board_contour": [
                {"x": int(point[0]), "y": int(point[1])} for point in polygon
            ],
            "board_mask_method": method,
            "timestamp": time.time(),
        }

    def detect_standard(self, img):
        """Standard HSV target detection for feeder etc.: return the valid contour closest to the image center."""
        if img is None or self.config is None:
            return _make_empty_result(self.target_name)

        h, w = img.shape[:2]
        center_x, center_y = w // 2, h // 2
        mask, detected_pixels, total_pixels, coverage, _ = _build_hsv_mask(
            img, self.config
        )

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        min_area = _safe_float(self.config.get("min_area", 50), 50)

        best = None
        best_dist = float("inf")
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_area:
                continue

            cx, cy = _contour_center(contour)
            dist = (cx - center_x) ** 2 + (cy - center_y) ** 2
            if dist < best_dist:
                best_dist = dist
                best = (contour, cx, cy, area)

        if best is None:
            return _make_empty_result(
                self.target_name, img.shape, detected_pixels, total_pixels, coverage
            )

        contour, cx, cy, _ = best
        rect_x, rect_y, rect_w, rect_h = cv2.boundingRect(contour)
        center_deadband_px = _safe_float(
            self.config.get("center_deadband_px", 1.5), 1.5
        )
        offset_x = _quantize_center_offset(cx - center_x, center_deadband_px)
        offset_y = _quantize_center_offset(cy - center_y, center_deadband_px)

        return {
            "found": True,
            "target_type": self.target_name,
            "center_x": int(center_x),
            "center_y": int(center_y),
            "target_x": int(round(cx)),
            "target_y": int(round(cy)),
            "offset_x": int(offset_x),
            "offset_y": int(offset_y),
            "rect_x": int(rect_x),
            "rect_y": int(rect_y),
            "rect_width": int(rect_w),
            "rect_height": int(rect_h),
            "detected_pixels": int(detected_pixels),
            "total_pixels": int(total_pixels),
            "coverage_percent": round(float(coverage), 2),
            "timestamp": time.time(),
        }

    def _board_mask_candidates(self, img):
        """Generate board candidate masks: prioritize configured HSV, with white board HSV fallback."""
        candidates = []

        # 1) Fully follow config, compatible with existing Japkit-generated configs.
        mask, detected_pixels, total_pixels, coverage, roi_box = _build_hsv_mask(
            img, self.config
        )
        candidates.append(
            ("configured_hsv", mask, detected_pixels, total_pixels, coverage, roi_box)
        )

        # 2) Retry ignoring invert: in some black/white board configs, invert deselects the white area.
        mask_no_inv, dp_no_inv, tp_no_inv, cov_no_inv, roi_box_no_inv = _build_hsv_mask(
            img, self.config, ignore_invert=True
        )
        candidates.append(
            (
                "configured_hsv_no_invert",
                mask_no_inv,
                dp_no_inv,
                tp_no_inv,
                cov_no_inv,
                roi_box_no_inv,
            )
        )

        # 3) HSV fallback specifically for white board on black background: uses HSV S/V channels, low saturation + high brightness.
        x, y, roi_w, roi_h = _clamp_roi(img.shape, self.config.get("roi"))
        roi_img = img[y : y + roi_h, x : x + roi_w]
        hsv = cv2.cvtColor(roi_img, cv2.COLOR_BGR2HSV)
        S = hsv[:, :, 1]
        V = hsv[:, :, 2]

        board_s_max = _safe_int(self.config.get("board_s_max", 90), 90)
        board_s_max = max(30, min(board_s_max, 220))
        board_v_floor = _safe_int(self.config.get("board_v_floor", 60), 60)
        board_v_floor = max(0, min(board_v_floor, 250))

        try:
            # Otsu adaptive threshold on V channel only, suitable for white board on black background and slight exposure changes.
            blur_v = cv2.GaussianBlur(V, (5, 5), 0)
            otsu_threshold, _ = cv2.threshold(
                blur_v, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
            )
            v_min = max(board_v_floor, int(otsu_threshold))
        except Exception:
            v_min = max(board_v_floor, 100)

        white_mask_roi = ((S <= board_s_max) & (V >= v_min)).astype(np.uint8) * 255
        white_mask = np.zeros(img.shape[:2], dtype=np.uint8)
        white_mask[y : y + roi_h, x : x + roi_w] = white_mask_roi
        white_detected = int(np.count_nonzero(white_mask_roi))
        white_total = int(roi_w * roi_h)
        white_cov = (white_detected / white_total * 100.0) if white_total > 0 else 0.0
        candidates.append(
            (
                "white_board_hsv_sv",
                white_mask,
                white_detected,
                white_total,
                white_cov,
                (x, y, roi_w, roi_h),
            )
        )

        return candidates

    def detect_board(self, img):
        """Detect the top-left corner of the PCB: only accept "board body outer contour LT + right ray + down ray".

        Key corrections:
        - No longer use ROI long rows/columns to directly set edges, avoiding drawing ROI top-left as PCB corner.
        - First find connected PCB body within the ROI mask, then use that body's bounding box/edges as PCB edges.
        - Hardcoded for current scene: only return PCB top-left corner; two edges must be flush with board body, one going right, one going down.
        - Disable configured_hsv_no_invert by default, to avoid treating gray baseboard/ROI background as board body.
        """
        if img is None or self.config is None:
            return _make_empty_result("board")

        h, w = img.shape[:2]
        center_x, center_y = w // 2, h // 2

        def _fit_angle(points, fallback=0.0):
            try:
                pts = np.array(points, dtype=np.float32)
                if pts.shape[0] < 6:
                    return float(fallback)
                vx, vy, x0, y0 = cv2.fitLine(pts, cv2.DIST_L2, 0, 0.01, 0.01).flatten()
                return _normalize_line_angle(
                    math.degrees(math.atan2(float(vy), float(vx)))
                )
            except Exception:
                return float(fallback)

        def _mask_circle_holes(mask, circles, expand_px):
            # Only fill holes, no hard filtering; circular holes do not participate in determining PCB vertices.
            if mask is None or not circles:
                return mask
            out = mask.copy()
            for cx, cy, r in circles:
                cv2.circle(out, (int(cx), int(cy)), int(r + expand_px), 255, -1)
            return out

        best = None
        fallback_best = None
        hsv_invert = bool(self.config.get("hsv_thresholds", {}).get("invert", False))
        min_area_abs = _safe_float(self.config.get("board_min_area", 350), 350)
        min_area_ratio = _safe_float(
            self.config.get("board_min_area_ratio", 0.018), 0.018
        )

        for (
            method,
            raw_mask,
            detected_pixels,
            total_pixels,
            coverage,
            roi_box,
        ) in self._board_mask_candidates(img):
            roi_x, roi_y, roi_w, roi_h = roi_box
            if roi_w <= 20 or roi_h <= 20:
                continue

            # In current green PCB scenes, configured_hsv_no_invert selects the gray baseboard/ROI background,
            # which is why the blue line attaches to the ROI top-left. Disabled by default.
            if (
                method == "configured_hsv_no_invert"
                and hsv_invert
                and not bool(self.config.get("board_allow_no_invert", False))
            ):
                continue
            if method == "white_board_hsv_sv" and not bool(
                self.config.get("board_allow_white_fallback", False)
            ):
                continue

            processed = _preprocess_board_mask(raw_mask, self.config, roi_box)

            # Circle holes only fill gaps for continuous edge statistics; do not use circle holes to determine candidate corners.
            circles = []
            if bool(self.config.get("board_enable_circle_fill", True)):
                try:
                    circles = _detect_dark_circles_in_roi(img, roi_box, self.config)
                    processed = _mask_circle_holes(
                        processed,
                        circles,
                        _safe_int(self.config.get("board_circle_fill_expand_px", 5), 5),
                    )
                    processed = _fill_holes(processed)
                except Exception:
                    circles = []

            roi_mask = processed[roi_y : roi_y + roi_h, roi_x : roi_x + roi_w]
            if roi_mask.size == 0:
                continue

            # Small closing is enough; large kernel would swallow the ROI background into one block.
            edge_k = _odd_kernel_size(
                self.config.get("board_edge_close_kernel", 5), 3, 15
            )
            edge_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (edge_k, edge_k))
            roi_mask = cv2.morphologyEx(
                roi_mask, cv2.MORPH_CLOSE, edge_kernel, iterations=1
            )
            roi_mask = _fill_holes(roi_mask)

            roi_nonzero = int(np.count_nonzero(roi_mask))
            roi_coverage = roi_nonzero / float(max(1, roi_w * roi_h)) * 100.0
            # Coverage only filters extreme errors: high coverage is basically ROI/baseboard, low coverage is hole/silkscreen fragments.
            if roi_coverage < _safe_float(
                self.config.get("board_min_roi_coverage", 2.0), 2.0
            ):
                continue
            if roi_coverage > _safe_float(
                self.config.get("board_max_roi_coverage", 80.0), 80.0
            ):
                continue

            if bool(self.config.get("board_allow_mask_bbox_fallback", True)):
                mask_ys, mask_xs = np.where(roi_mask > 0)
                if len(mask_xs) > 0 and len(mask_ys) > 0:
                    x0 = int(np.min(mask_xs))
                    y0 = int(np.min(mask_ys))
                    x1 = int(np.max(mask_xs))
                    y1 = int(np.max(mask_ys))
                    bw = int(x1 - x0 + 1)
                    bh = int(y1 - y0 + 1)
                    if bw >= 20 and bh >= 20:
                        lt = np.array([x0 + roi_x, y0 + roi_y], dtype=np.float32)
                        rt = np.array([x1 + roi_x, y0 + roi_y], dtype=np.float32)
                        rb = np.array([x1 + roi_x, y1 + roi_y], dtype=np.float32)
                        lb = np.array([x0 + roi_x, y1 + roi_y], dtype=np.float32)
                        corners = np.array([lt, rt, rb, lb], dtype=np.float32)
                        area = float(roi_nonzero)
                        comp_fill = area / float(max(1, bw * bh))
                        target_x = int(round(float(lt[0])))
                        target_y = int(round(float(lt[1])))
                        dist_penalty = 1.0 / (
                            1.0
                            + 0.00002
                            * ((target_x - center_x) ** 2 + (target_y - center_y) ** 2)
                        )
                        score = area * max(0.20, min(1.0, comp_fill)) * dist_penalty
                        bbox_edges = [
                            {
                                "name": "right",
                                "start_x": int(round(float(lt[0]))),
                                "start_y": int(round(float(lt[1]))),
                                "end_x": int(round(float(rt[0]))),
                                "end_y": int(round(float(rt[1]))),
                                "length": round(_point_distance(lt, rt), 2),
                                "angle_deg": 0.0,
                            },
                            {
                                "name": "down",
                                "start_x": int(round(float(lt[0]))),
                                "start_y": int(round(float(lt[1]))),
                                "end_x": int(round(float(lb[0]))),
                                "end_y": int(round(float(lb[1]))),
                                "length": round(_point_distance(lt, lb), 2),
                                "angle_deg": 90.0,
                            },
                        ]
                        bbox_all_edges = [
                            bbox_edges[0],
                            {
                                "start_x": int(rt[0]),
                                "start_y": int(rt[1]),
                                "end_x": int(rb[0]),
                                "end_y": int(rb[1]),
                                "length": round(_point_distance(rt, rb), 2),
                                "angle_deg": 90.0,
                            },
                            {
                                "start_x": int(rb[0]),
                                "start_y": int(rb[1]),
                                "end_x": int(lb[0]),
                                "end_y": int(lb[1]),
                                "length": round(_point_distance(rb, lb), 2),
                                "angle_deg": 0.0,
                            },
                            bbox_edges[1],
                        ]
                        bbox_candidate = {
                            "score": float(score),
                            "method": method + "_mask_bbox_fallback",
                            "detected_pixels": int(area),
                            "total_pixels": int(roi_w * roi_h),
                            "coverage": float(roi_coverage),
                            "roi_box": roi_box,
                            "corners": corners,
                            "corner_idx": 0,
                            "corner_mode": "lt_mask_bbox_hsv_fallback",
                            "corner": lt,
                            "all_edges": bbox_all_edges,
                            "selected_edges": bbox_edges,
                            "angle": 0.0,
                            "long_angle": float(0.0 if bw >= bh else 90.0),
                            "rect": (
                                int(x0 + roi_x),
                                int(y0 + roi_y),

                                int(bw),
                                int(bh),
                            ),
                            "area": float(area),
                            "rect_area": float(max(1, bw * bh)),
                            "fill_ratio": float(comp_fill),
                            "roi_guard_px": float(
                                min(
                                    _get_board_roi_guard_margin(self.config, roi_box),
                                    _safe_float(
                                        self.config.get("board_run_guard_max_px", 18),
                                        18,
                                    ),
                                )
                            ),
                            "corner_edge_distance": float(
                                _point_roi_edge_distance(lt, roi_box)
                            ),
                            "circles": circles,
                            "right_cov": 0.0,
                            "down_cov": 0.0,
                        }
                        if (
                            fallback_best is None
                            or bbox_candidate["score"] > fallback_best["score"]
                        ):
                            fallback_best = bbox_candidate

            # Only find PCB body connected components within the ROI, avoiding using ROI top-left as edges.
            comp_mask_input = (roi_mask > 0).astype(np.uint8)
            num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
                comp_mask_input, connectivity=8
            )
            required_area = max(min_area_abs, float(roi_w * roi_h) * min_area_ratio)

            for label in range(1, num_labels):
                area = float(stats[label, cv2.CC_STAT_AREA])
                if area < required_area:
                    continue

                x0 = int(stats[label, cv2.CC_STAT_LEFT])
                y0 = int(stats[label, cv2.CC_STAT_TOP])
                bw = int(stats[label, cv2.CC_STAT_WIDTH])
                bh = int(stats[label, cv2.CC_STAT_HEIGHT])
                if bw <= 8 or bh <= 8:
                    continue

                # Filter small local structures: PCB body must form obvious right/down extensions in the current ROI.
                min_w = max(
                    _safe_int(self.config.get("board_min_right_ray_len_px", 45), 45),
                    int(
                        roi_w
                        * _safe_float(
                            self.config.get("board_min_right_ray_len_ratio", 0.16), 0.16
                        )
                    ),
                )
                min_h = max(
                    _safe_int(self.config.get("board_min_down_ray_len_px", 45), 45),
                    int(
                        roi_h
                        * _safe_float(
                            self.config.get("board_min_down_ray_len_ratio", 0.16), 0.16
                        )
                    ),
                )
                if bw < min_w or bh < min_h:
                    continue

                guard = min(
                    _get_board_roi_guard_margin(self.config, roi_box),
                    _safe_float(self.config.get("board_run_guard_max_px", 18), 18),
                )
                comp_mask = ((labels == label).astype(np.uint8)) * 255

                # Keep a conservative HSV-component fallback. The strict ray/guard
                # checks are still preferred, but real PCBs may sit close to the ROI
                # edge or have silkscreen/holes that break ray coverage.
                lt = np.array([x0 + roi_x, y0 + roi_y], dtype=np.float32)
                rt = np.array([x0 + bw - 1 + roi_x, y0 + roi_y], dtype=np.float32)
                rb = np.array(
                    [x0 + bw - 1 + roi_x, y0 + bh - 1 + roi_y], dtype=np.float32
                )
                lb = np.array([x0 + roi_x, y0 + bh - 1 + roi_y], dtype=np.float32)
                corners = np.array([lt, rt, rb, lb], dtype=np.float32)
                comp_fill = area / float(max(1, bw * bh))
                target_x = int(round(float(lt[0])))
                target_y = int(round(float(lt[1])))
                dist_penalty = 1.0 / (
                    1.0
                    + 0.00002
                    * ((target_x - center_x) ** 2 + (target_y - center_y) ** 2)
                )
                score = area * max(0.35, min(1.0, comp_fill)) * dist_penalty
                fallback_edges = [
                    {
                        "name": "right",
                        "start_x": int(round(float(lt[0]))),
                        "start_y": int(round(float(lt[1]))),
                        "end_x": int(round(float(rt[0]))),
                        "end_y": int(round(float(rt[1]))),
                        "length": round(_point_distance(lt, rt), 2),
                        "angle_deg": 0.0,
                    },
                    {
                        "name": "down",
                        "start_x": int(round(float(lt[0]))),
                        "start_y": int(round(float(lt[1]))),
                        "end_x": int(round(float(lb[0]))),
                        "end_y": int(round(float(lb[1]))),
                        "length": round(_point_distance(lt, lb), 2),
                        "angle_deg": 90.0,
                    },
                ]
                fallback_all_edges = [
                    fallback_edges[0],
                    {
                        "start_x": int(rt[0]),
                        "start_y": int(rt[1]),
                        "end_x": int(rb[0]),
                        "end_y": int(rb[1]),
                        "length": round(_point_distance(rt, rb), 2),
                        "angle_deg": 90.0,
                    },
                    {
                        "start_x": int(rb[0]),
                        "start_y": int(rb[1]),
                        "end_x": int(lb[0]),
                        "end_y": int(lb[1]),
                        "length": round(_point_distance(rb, lb), 2),
                        "angle_deg": 0.0,
                    },
                    fallback_edges[1],
                ]
                fallback_candidate = {
                    "score": float(score),
                    "method": method + "_component_ltop_fallback",
                    "detected_pixels": int(area),
                    "total_pixels": int(roi_w * roi_h),
                    "coverage": float(roi_coverage),
                    "roi_box": roi_box,
                    "corners": corners,
                    "corner_idx": 0,
                    "corner_mode": "lt_component_hsv_fallback",
                    "corner": lt,
                    "all_edges": fallback_all_edges,
                    "selected_edges": fallback_edges,
                    "angle": 0.0,
                    "long_angle": float(0.0 if bw >= bh else 90.0),
                    "rect": (int(x0 + roi_x), int(y0 + roi_y), int(bw), int(bh)),

                    "area": float(area),
                    "rect_area": float(max(1, bw * bh)),
                    "fill_ratio": float(comp_fill),
                    "roi_guard_px": float(guard),
                    "corner_edge_distance": float(
                        _point_roi_edge_distance(lt, roi_box)
                    ),
                    "circles": circles,
                    "right_cov": 0.0,
                    "down_cov": 0.0,
                }
                if fallback_best is None or score > fallback_best["score"]:
                    fallback_best = fallback_candidate

                # Top-left corner must not be in the ROI top-left guard zone; otherwise it is a false corner from the ROI edge.
                if not bool(self.config.get("board_allow_roi_edge_corner", False)):
                    if x0 <= guard or y0 <= guard:
                        continue

                # Check two rays from the PCB body top-left corner: top edge going right, left edge going down.
                ray_band = max(
                    2,
                    min(
                        _safe_int(self.config.get("board_ray_check_band_px", 6), 6), 14
                    ),
                )
                min_ray_cov = _safe_float(
                    self.config.get("board_min_ray_coverage", 0.28), 0.28
                )
                start_tol = _safe_int(
                    self.config.get("board_ray_start_tolerance_px", 14), 14
                )

                top_y0 = max(0, y0 - ray_band)
                top_y1 = min(roi_h, y0 + ray_band + 1)
                left_x0 = max(0, x0 - ray_band)
                left_x1 = min(roi_w, x0 + ray_band + 1)

                right_window = comp_mask[top_y0:top_y1, x0 : min(roi_w, x0 + min_w)]
                down_window = comp_mask[y0 : min(roi_h, y0 + min_h), left_x0:left_x1]
                if right_window.size == 0 or down_window.size == 0:
                    continue
                right_cov = float(np.count_nonzero(right_window)) / float(
                    right_window.size
                )
                down_cov = float(np.count_nonzero(down_window)) / float(
                    down_window.size
                )
                if right_cov < min_ray_cov or down_cov < min_ray_cov:
                    continue

                top_cols = np.where(
                    np.count_nonzero(comp_mask[top_y0:top_y1, :], axis=0) > 0
                )[0]
                left_rows = np.where(
                    np.count_nonzero(comp_mask[:, left_x0:left_x1], axis=1) > 0
                )[0]
                if len(top_cols) == 0 or len(left_rows) == 0:
                    continue
                if int(top_cols[0]) > x0 + start_tol:
                    continue
                if int(top_cols[-1]) < x0 + min_w:
                    continue
                if int(left_rows[0]) > y0 + start_tol:
                    continue
                if int(left_rows[-1]) < y0 + min_h:
                    continue

                # Fit angle using points near the connected component edges; final rendering is flush with PCB body bbox.
                fit_band = max(
                    2,
                    min(_safe_int(self.config.get("board_edge_fit_band_px", 5), 5), 12),
                )
                top_band = comp_mask[
                    max(0, y0 - fit_band) : min(roi_h, y0 + fit_band + 1), x0 : x0 + bw
                ]
                left_band = comp_mask[
                    y0 : y0 + bh, max(0, x0 - fit_band) : min(roi_w, x0 + fit_band + 1)
                ]
                top_pts_y, top_pts_x = np.where(top_band > 0)
                left_pts_y, left_pts_x = np.where(left_band > 0)
                top_points = [
                    (int(x0 + x + roi_x), int(max(0, y0 - fit_band) + y + roi_y))
                    for y, x in zip(top_pts_y, top_pts_x)
                ]
                left_points = [
                    (int(max(0, x0 - fit_band) + x + roi_x), int(y0 + y + roi_y))
                    for y, x in zip(left_pts_y, left_pts_x)
                ]
                top_angle = _fit_angle(top_points, 0.0)
                left_angle = _normalize_line_angle(_fit_angle(left_points, 90.0))

                selected_edges = [
                    {
                        "name": "right",
                        "start_x": int(round(float(lt[0]))),
                        "start_y": int(round(float(lt[1]))),
                        "end_x": int(round(float(rt[0]))),
                        "end_y": int(round(float(rt[1]))),
                        "length": round(_point_distance(lt, rt), 2),
                        "angle_deg": round(float(top_angle), 2),
                    },
                    {
                        "name": "down",
                        "start_x": int(round(float(lt[0]))),
                        "start_y": int(round(float(lt[1]))),
                        "end_x": int(round(float(lb[0]))),
                        "end_y": int(round(float(lb[1]))),
                        "length": round(_point_distance(lt, lb), 2),
                        "angle_deg": round(float(left_angle), 2),
                    },
                ]
                all_edges = [
                    selected_edges[0],
                    {
                        "start_x": int(rt[0]),
                        "start_y": int(rt[1]),
                        "end_x": int(rb[0]),
                        "end_y": int(rb[1]),
                        "length": round(_point_distance(rt, rb), 2),
                        "angle_deg": round(float(left_angle), 2),
                    },
                    {
                        "start_x": int(rb[0]),
                        "start_y": int(rb[1]),
                        "end_x": int(lb[0]),
                        "end_y": int(lb[1]),
                        "length": round(_point_distance(rb, lb), 2),
                        "angle_deg": round(float(top_angle), 2),
                    },
                    selected_edges[1],
                ]

                if best is None or score > best["score"]:
                    best = {
                        "score": float(score),
                        "method": method + "_component_ltop_edges",
                        "detected_pixels": int(area),
                        "total_pixels": int(roi_w * roi_h),
                        "coverage": float(roi_coverage),
                        "roi_box": roi_box,
                        "corners": corners,
                        "corner_idx": 0,
                        "corner_mode": "lt_component_right_down",
                        "corner": lt,
                        "all_edges": all_edges,
                        "selected_edges": selected_edges,
                        "angle": float(top_angle),
                        "long_angle": float(top_angle if bw >= bh else left_angle),
                        "rect": (int(x0 + roi_x), int(y0 + roi_y), int(bw), int(bh)),

                        "area": float(area),
                        "rect_area": float(max(1, bw * bh)),
                        "fill_ratio": float(comp_fill),
                        "roi_guard_px": float(guard),
                        "corner_edge_distance": float(
                            _point_roi_edge_distance(lt, roi_box)
                        ),
                        "circles": circles,
                        "right_cov": float(right_cov),
                        "down_cov": float(down_cov),
                    }

        if best is None and bool(
            self.config.get("board_allow_component_fallback", True)
        ):
            best = fallback_best

        if best is None:
            _, detected_pixels, total_pixels, coverage, _ = _build_hsv_mask(
                img, self.config
            )
            return _make_empty_result(
                "board",
                img.shape,
                detected_pixels,
                total_pixels,
                coverage,
                message="Could not find top-left corner adjacent to PCB body: filtered ROI top-left, gray baseboard, and local holes/silkscreen",
            )

        corner = best["corner"]
        target_x = int(round(float(corner[0])))
        target_y = int(round(float(corner[1])))
        offset_x = int(target_x - center_x)
        offset_y = int(target_y - center_y)
        rect_x, rect_y, rect_w, rect_h = best["rect"]
        board_center_x = int(rect_x + rect_w / 2)
        board_center_y = int(rect_y + rect_h / 2)

        return {
            "found": True,
            "target_type": "board",
            "center_x": int(center_x),
            "center_y": int(center_y),
            "target_x": int(target_x),
            "target_y": int(target_y),
            "offset_x": int(offset_x),
            "offset_y": int(offset_y),
            "rect_x": int(rect_x),
            "rect_y": int(rect_y),
            "rect_width": int(rect_w),
            "rect_height": int(rect_h),
            "detected_pixels": int(best["detected_pixels"]),
            "total_pixels": int(best["total_pixels"]),
            "coverage_percent": round(float(best["coverage"]), 2),
            "timestamp": time.time(),
            "board_found": True,
            "board_center_x": int(board_center_x),
            "board_center_y": int(board_center_y),
            "board_corner_x": int(target_x),
            "board_corner_y": int(target_y),
            "board_corner_index": 0,
            "board_corner_mode": best["corner_mode"],
            "board_corners": [
                {"x": int(round(float(p[0]))), "y": int(round(float(p[1])))}
                for p in best["corners"]
            ],
            "board_edges": best["selected_edges"],
            "board_all_edges": best["all_edges"],
            "board_angle_deg": round(float(best["angle"]), 2),
            "board_long_edge_angle_deg": round(float(best["long_angle"]), 2),
            "board_contour_area": round(float(best["area"]), 2),
            "board_raw_contour_area": round(float(best["area"]), 2),
            "board_body_bbox_long_px": round(float(max(rect_w, rect_h)), 2),
            "board_body_bbox_short_px": round(float(min(rect_w, rect_h)), 2),
            "board_rect_area": round(float(best["rect_area"]), 2),
            "board_fill_ratio": round(float(best["fill_ratio"]), 3),
            "board_mask_method": best["method"],
            "board_roi": {
                "x": int(best["roi_box"][0]),
                "y": int(best["roi_box"][1]),
                "width": int(best["roi_box"][2]),
                "height": int(best["roi_box"][3]),
            },
            "board_roi_guard_margin_px": round(float(best["roi_guard_px"]), 2),
            "board_corner_roi_edge_distance_px": round(
                float(best["corner_edge_distance"]), 2
            ),
            "board_box_guard_corner_count": 0,
            "board_bbox_coverage_percent": round(float(best["coverage"]), 2),
            "board_detected_circles": [
                {"x": int(c[0]), "y": int(c[1]), "r": int(c[2])}
                for c in best.get("circles", [])
            ],
            "board_force_left_top_right_down": True,
            "board_expected_corner": "lt",
            "board_expected_rays": ["right", "down"],
            "board_right_ray_coverage": round(float(best.get("right_cov", 0.0)), 3),
            "board_down_ray_coverage": round(float(best.get("down_cov", 0.0)), 3),
            "board_corner_near_circle": False,
            "board_corner_near_circle_info": None,
        }

    def detect_check(self, img):
        """Detect a held component against an empty bottom-camera reference."""
        return _component_check_detector.detect(self.camera_id, img, self.config)
