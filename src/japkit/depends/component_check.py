"""Bottom-camera empty-reference and held-component detection."""

import threading
import time

import cv2
import numpy as np

def _normalize_axis_angle(angle: float) -> float:
    while angle <= -90.0:
        angle += 180.0
    while angle > 90.0:
        angle -= 180.0
    return float(angle)


def _match_reference_illumination(reference, current):
    """Match current-frame luminance to the empty reference robustly."""
    h, w = reference.shape[:2]
    sample_mask = np.ones((h, w), dtype=bool)
    # The held component occupies the center. Exclude it while estimating the
    # exposure transform so the component itself cannot bias normalization.
    half_w = min(w // 3, 70)
    half_h = min(h // 3, 55)
    cx, cy = w // 2, h // 2
    sample_mask[cy - half_h : cy + half_h, cx - half_w : cx + half_w] = False
    ref_values = reference[sample_mask].astype(np.float32)
    cur_values = current[sample_mask].astype(np.float32)
    if ref_values.size < 100 or cur_values.size < 100:
        return current, 0.0
    ref_low, ref_high = np.percentile(ref_values, (10.0, 90.0))
    cur_low, cur_high = np.percentile(cur_values, (10.0, 90.0))
    scale = float(ref_high - ref_low) / max(8.0, float(cur_high - cur_low))
    scale = max(0.65, min(1.55, scale))
    offset = float(ref_low) - scale * float(cur_low)
    normalized = np.clip(current.astype(np.float32) * scale + offset, 0, 255)
    drift = float(np.median(np.abs(normalized[sample_mask] - reference[sample_mask])))
    return normalized.astype(np.uint8), drift


class ComponentCheckDetector:
    """Detect a newly introduced, rectangular part against an empty camera view.

    The workflow switches camera 2 to ``check`` before moving a nozzle over it.
    The first frames therefore form an empty reference.  Subsequent frames are
    differenced against that reference, which is substantially more reliable
    than a fixed colour threshold for parts of different body colours.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._states = {}
        self._active_profiles = {}

    def select_profile(self, camera_id: int, profile: str, reset=False) -> None:
        camera_id = int(camera_id)
        profile = str(profile or "default").strip().upper()
        with self._lock:
            self._active_profiles[camera_id] = profile
            key = (camera_id, profile)
            if reset or key not in self._states:
                self._states[key] = {"frames": [], "reference": None}

    def reset(self, camera_id: int, profile: str = "default") -> None:
        self.select_profile(camera_id, profile, reset=True)

    def _empty(self, img, ready=False, message=""):
        h, w = img.shape[:2]
        return {
            "found": False,
            "target_type": "check",
            "center_x": int(w // 2),
            "center_y": int(h // 2),
            "target_x": 0,
            "target_y": 0,
            "offset_x": 0,
            "offset_y": 0,
            "coverage_percent": 0.0,
            "component_angle_deg": 0.0,
            "component_area_px": 0.0,
            "component_aspect_ratio": 0.0,
            "angle_confidence": 0.0,
            "reference_ready": bool(ready),
            "implemented": True,
            "timestamp": time.time(),
            "message": message,
        }

    def detect(self, camera_id: int, img, config=None):
        if img is None:
            return {
                "found": False,
                "target_type": "check",
                "reference_ready": False,
                "implemented": True,
                "timestamp": time.time(),
                "message": "camera frame unavailable",
            }

        config = config or {}
        algorithm = str(config.get("algorithm", "")).lower()
        if algorithm == "hsv":
            return self._detect_hsv(img, config)

        camera_id = int(camera_id)
        with self._lock:
            profile = self._active_profiles.get(camera_id, "DEFAULT")
        state_key = (camera_id, profile)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        required = max(3, int(config.get("reference_samples", 5) or 5))

        with self._lock:
            state = self._states.setdefault(
                state_key, {"frames": [], "reference": None}
            )
            if state["reference"] is None:
                state["frames"].append(gray.copy())
                if len(state["frames"]) >= required:
                    state["reference"] = np.median(
                        np.stack(state["frames"][-required:], axis=0), axis=0
                    ).astype(np.uint8)
                    state["frames"].clear()
                ready = state["reference"] is not None
                result = self._empty(
                    img,
                    ready=ready,
                    message=(
                        "empty reference ready"
                        if ready
                        else "capturing empty reference"
                    ),
                )
                result["reference_profile"] = profile
                return result
            reference = state["reference"].copy()

        exposure_width = min(
            img.shape[1], max(48, int(config.get("exposure_roi_width", 180) or 180))
        )
        exposure_height = min(
            img.shape[0], max(48, int(config.get("exposure_roi_height", 150) or 150))
        )
        exposure_x0 = (img.shape[1] - exposure_width) // 2
        exposure_y0 = (img.shape[0] - exposure_height) // 2
        exposure_roi = img[
            exposure_y0 : exposure_y0 + exposure_height,
            exposure_x0 : exposure_x0 + exposure_width,
        ]
        exposure_gray = cv2.cvtColor(exposure_roi, cv2.COLOR_BGR2GRAY)
        white_ratio = float(np.mean(np.min(exposure_roi, axis=2) >= 245))
        luma_saturated_ratio = float(np.mean(exposure_gray >= 250))
        exposure_median = float(np.median(exposure_gray))
        exposure_metrics = {
            "white_ratio": round(white_ratio, 4),
            "luma_saturated_ratio": round(luma_saturated_ratio, 4),
            "exposure_median": round(exposure_median, 2),
        }
        if (
            white_ratio > float(config.get("max_white_ratio", 0.12) or 0.12)
            or luma_saturated_ratio
            > float(config.get("max_luma_saturated_ratio", 0.35) or 0.35)
            or exposure_median
            > float(config.get("max_exposure_median", 235.0) or 235.0)
        ):
            result = self._empty(
                img, ready=True, message="bottom-camera frame overexposed"
            )
            result.update(
                {
                    "status": "FRAME_OVEREXPOSED",
                    "reference_profile": profile,
                    **exposure_metrics,
                }
            )
            return result

        h, w = gray.shape[:2]
        roi_width = min(w, max(80, int(config.get("roi_width", 360) or 360)))
        roi_height = min(h, max(80, int(config.get("roi_height", 300) or 300)))
        x0 = (w - roi_width) // 2
        y0 = (h - roi_height) // 2
        x1, y1 = x0 + roi_width, y0 + roi_height

        reference_roi = reference[y0:y1, x0:x1]
        current_roi, illumination_drift = _match_reference_illumination(
            reference_roi, gray[y0:y1, x0:x1]
        )
        diff = cv2.absdiff(reference_roi, current_roi)
        threshold_floor = max(5, int(config.get("min_diff_threshold", 16) or 16))
        otsu_threshold, mask = cv2.threshold(
            diff, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        if otsu_threshold < threshold_floor:
            _, mask = cv2.threshold(diff, threshold_floor, 255, cv2.THRESH_BINARY)
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        min_area = float(config.get("min_component_area_px", 70) or 70)
        max_area = float(config.get("max_component_area_px", 12000) or 12000)
        min_aspect = float(config.get("min_aspect_ratio", 1.12) or 1.12)
        max_distance = float(config.get("max_center_distance_px", 110) or 110)
        max_span = float(config.get("max_component_span_px", 90) or 90)
        contact_margin = float(config.get("center_contact_margin_px", 8) or 8)
        image_center = np.array([w / 2.0, h / 2.0], dtype=np.float32)

        best = None
        for contour in contours:
            area = float(cv2.contourArea(contour))
            if area < min_area or area > max_area:
                continue
            shifted = contour.astype(np.float32)
            shifted[:, 0, 0] += x0
            shifted[:, 0, 1] += y0
            rect = cv2.minAreaRect(shifted)
            (cx, cy), (rw, rh), angle = rect
            short = min(float(rw), float(rh))
            long = max(float(rw), float(rh))
            if short < 2.0 or long < 3.0:
                continue
            if long > max_span:
                continue
            aspect = long / short
            distance = float(np.linalg.norm(np.array([cx, cy]) - image_center))
            if distance > max_distance or aspect < min_aspect:
                continue
            if cv2.pointPolygonTest(
                shifted.astype(np.float32),
                (float(image_center[0]), float(image_center[1])),
                True,
            ) < -contact_margin:
                continue
            rect_area = max(1.0, float(rw) * float(rh))
            rectangularity = min(1.0, area / rect_area)
            score = distance + 35.0 / max(aspect, 1.0) - 12.0 * rectangularity
            if best is None or score < best[0]:
                best = (score, shifted, rect, area, aspect, rectangularity)

        # Bright ceramic/passive bodies can merge with ring-light changes in
        # the absolute-difference mask. A high positive-only delta isolates the
        # newly introduced body while rejecting the empty nozzle aperture.
        signed_delta = current_roi.astype(np.int16) - reference_roi.astype(np.int16)
        bright_threshold = max(
            20, int(config.get("bright_component_threshold", 55) or 55)
        )
        bright_mask = (signed_delta >= bright_threshold).astype(np.uint8) * 255
        bright_mask = cv2.morphologyEx(
            bright_mask, cv2.MORPH_OPEN, kernel, iterations=1
        )
        bright_mask = cv2.morphologyEx(
            bright_mask, cv2.MORPH_CLOSE, kernel, iterations=1
        )
        bright_contours, _ = cv2.findContours(
            bright_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        bright_best = None
        bright_min_area = float(
            config.get("bright_min_component_area_px", 100) or 100
        )
        bright_max_area = float(
            config.get("bright_max_component_area_px", 3000) or 3000
        )
        bright_max_span = float(
            config.get("bright_max_component_span_px", 60) or 60
        )
        for contour in bright_contours:
            area = float(cv2.contourArea(contour))
            if area < bright_min_area or area > bright_max_area:
                continue
            shifted = contour.astype(np.float32)
            shifted[:, 0, 0] += x0
            shifted[:, 0, 1] += y0
            rect = cv2.minAreaRect(shifted)
            (cx, cy), (rw, rh), _ = rect
            short = min(float(rw), float(rh))
            long = max(float(rw), float(rh))
            if short < 3.0 or long > bright_max_span:
                continue
            distance = float(np.linalg.norm(np.array([cx, cy]) - image_center))
            if distance > max_distance:
                continue
            if cv2.pointPolygonTest(
                shifted,
                (float(image_center[0]), float(image_center[1])),
                True,
            ) < -contact_margin:
                continue
            aspect = long / max(1.0, short)
            rect_area = max(1.0, float(rw) * float(rh))
            rectangularity = min(1.0, area / rect_area)
            score = distance + 12.0 * (1.0 - rectangularity)
            if bright_best is None or score < bright_best[0]:
                bright_best = (
                    score,
                    shifted,
                    rect,
                    area,
                    aspect,
                    rectangularity,
                )
        detection_method = "absolute_difference"
        if bright_best is not None:
            best = bright_best
            detection_method = "positive_brightness_difference"

        if best is None:
            result = self._empty(img, ready=True, message="held component not found")
            result["changed_pixels"] = int(cv2.countNonZero(mask))
            result["illumination_drift"] = round(illumination_drift, 3)
            result["reference_profile"] = profile
            result.update(exposure_metrics)
            return result

        _, contour, rect, area, aspect, rectangularity = best
        (cx, cy), (rw, rh), angle = rect
        # For near-square components (aspect < 1.3), minAreaRect has orientation ambiguity
        # (0deg and 90deg bounding rects are identical); angle is unreliable: skip +90deg flip
        # heuristic and set angle_confidence to 0.
        near_square = aspect < 1.3
        if rw < rh and not near_square:
            angle += 90.0
        angle = _normalize_axis_angle(angle)
        box = cv2.boxPoints(rect).astype(int).tolist()
        confidence = 0.0 if near_square else max(0.0, min(1.0, (aspect - 1.0) / 1.5))
        offset_x = float(cx - w / 2.0)
        offset_y = float(cy - h / 2.0)
        return {
            "found": True,
            "target_type": "check",
            "center_x": int(w // 2),
            "center_y": int(h // 2),
            "target_x": round(float(cx), 3),
            "target_y": round(float(cy), 3),
            "offset_x": round(offset_x, 3),
            "offset_y": round(offset_y, 3),
            "coverage_percent": round(
                100.0 * area / max(1.0, roi_width * roi_height), 3
            ),
            "component_angle_deg": round(angle, 3),
            "component_area_px": round(area, 3),
            "component_aspect_ratio": round(aspect, 3),
            "component_rectangularity": round(rectangularity, 3),
            "angle_confidence": round(confidence, 3),
            "reference_ready": True,
            "implemented": True,
            "box": box,
            "changed_pixels": int(cv2.countNonZero(mask)),
            "illumination_drift": round(illumination_drift, 3),
            "timestamp": time.time(),
            "message": "held component detected",
            "reference_profile": profile,
            "detection_method": detection_method,
            **exposure_metrics,
        }

    def _detect_hsv(self, img, config):
        """HSV-based detection - uses config from picks/check_result.json.
        Finds the rectangle contour closest to image center."""
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        thresholds = config.get("hsv_thresholds", {})
        s_min = int(thresholds.get("S_min", 25))
        s_max = int(thresholds.get("S_max", 199))
        v_min = int(thresholds.get("V_min", 120))
        v_max = int(thresholds.get("V_max", 255))
        invert = bool(thresholds.get("invert", True))
        lower = np.array([0, s_min, v_min])
        upper = np.array([180, s_max, v_max])
        mask = cv2.inRange(hsv, lower, upper)
        if invert:
            mask = cv2.bitwise_not(mask)

        roi = config.get("roi", {})
        if roi and all(k in roi for k in ("x", "y", "width", "height")):
            full_mask = np.zeros(mask.shape, dtype=np.uint8)
            rx, ry, rw, rh = (
                int(roi["x"]),
                int(roi["y"]),
                int(roi["width"]),
                int(roi["height"]),
            )
            rx = max(0, min(rx, mask.shape[1] - 1))
            ry = max(0, min(ry, mask.shape[0] - 1))
            rw = max(1, min(rw, mask.shape[1] - rx))
            rh = max(1, min(rh, mask.shape[0] - ry))
            full_mask[ry : ry + rh, rx : rx + rw] = mask[ry : ry + rh, rx : rx + rw]
            mask = full_mask

        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        h, w = img.shape[:2]
        image_center = np.array([w / 2.0, h / 2.0], dtype=np.float32)
        min_area = float(config.get("min_component_area_px", 50) or 50)
        max_area = float(config.get("max_component_area_px", 12000) or 12000)
        max_distance = float(config.get("max_center_distance_px", 110) or 110)
        min_aspect = float(config.get("min_aspect_ratio", 1.05) or 1.05)

        best = None
        for contour in contours:
            area = float(cv2.contourArea(contour))
            if area < min_area or area > max_area:
                continue
            rect = cv2.minAreaRect(contour)
            (cx, cy), (rw, rh), angle = rect
            short = min(float(rw), float(rh))
            long_val = max(float(rw), float(rh))
            if short < 2.0 or long_val < 3.0:
                continue
            aspect = long_val / short
            distance = float(np.linalg.norm(np.array([cx, cy]) - image_center))
            if distance > max_distance or aspect < min_aspect:
                continue
            if best is None or distance < best[0]:
                best = (distance, contour, rect, area, aspect)

        if best is None:
            result = self._empty(
                img, ready=True, message="held component not found (HSV)"
            )
            result["changed_pixels"] = int(cv2.countNonZero(mask))
            return result

        _, contour, rect, area, aspect = best
        (cx, cy), (rw, rh), angle = rect
        # Near-square component angle is unreliable (see same handling in detect())
        near_square = aspect < 1.3
        if rw < rh and not near_square:
            angle += 90.0
        angle = _normalize_axis_angle(angle)
        box = cv2.boxPoints(rect).astype(int).tolist()
        confidence = 0.0 if near_square else max(0.0, min(1.0, (aspect - 1.0) / 1.5))
        offset_x = float(cx - w / 2.0)
        offset_y = float(cy - h / 2.0)
        return {
            "found": True,
            "target_type": "check",
            "center_x": int(w // 2),
            "center_y": int(h // 2),
            "target_x": round(float(cx), 3),
            "target_y": round(float(cy), 3),
            "offset_x": round(offset_x, 3),
            "offset_y": round(offset_y, 3),
            "coverage_percent": round(100.0 * area / max(1.0, w * h), 3),
            "component_angle_deg": round(angle, 3),
            "component_area_px": round(area, 3),
            "component_aspect_ratio": round(aspect, 3),
            "angle_confidence": round(confidence, 3),
            "reference_ready": True,
            "implemented": True,
            "box": box,
            "changed_pixels": int(cv2.countNonZero(mask)),
            "timestamp": time.time(),
            "message": "held component detected (HSV)",
        }


_component_check_detector = ComponentCheckDetector()
