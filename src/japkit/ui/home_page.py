"""Full-screen Home page hosting the live 3D machine view."""
import math
import threading
import time
import urllib.error
import urllib.request

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QImage, QPalette, QPixmap
from PyQt5.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from depends.preview import Fetcher, GLW3D, GL_BACKEND, GL_OK


class VisionPreviewFetcher(threading.Thread):
    """Fetch rendered host-GUI camera frames without blocking Qt rendering."""

    def __init__(self, pi_url):
        super().__init__(daemon=True)
        self.pi_url = pi_url.rstrip("/")
        self.running = False
        self._cookie = ""
        self._active = {1: False, 2: False}
        self._frames = {1: None, 2: None}
        self._revisions = {1: 0, 2: 0}
        self._lock = threading.Lock()

    def set_cookie(self, cookie):
        with self._lock:
            self._cookie = cookie or ""

    def set_active(self, camera_id, active):
        camera_id = int(camera_id)
        with self._lock:
            active = bool(active)
            self._active[camera_id] = active
            if not active and self._frames[camera_id] is not None:
                self._frames[camera_id] = None
                self._revisions[camera_id] += 1

    def get_frame(self, camera_id):
        with self._lock:
            return self._frames[camera_id], self._revisions[camera_id]

    def run(self):
        self.running = True
        while self.running:
            started = time.monotonic()
            with self._lock:
                # Poll both endpoints. In older host telemetry payloads the
                # activity field may be missing, but a 200 JPEG is definitive.
                active_cameras = (1, 2)
                cookie = self._cookie
            for camera_id in active_cameras:
                if not self.running:
                    break
                try:
                    request = urllib.request.Request(
                        f"{self.pi_url}/api/vision-preview/cam{camera_id}",
                        headers={"Cookie": cookie, "Cache-Control": "no-cache"},
                    )
                    with urllib.request.urlopen(request, timeout=1.5) as response:
                        response_status = response.status
                        raw = response.read() if response_status == 200 else b""
                    if not raw:
                        if response_status == 204:
                            with self._lock:
                                if self._frames[camera_id] is not None:
                                    self._frames[camera_id] = None
                                    self._revisions[camera_id] += 1
                        continue
                    with self._lock:
                        self._frames[camera_id] = raw
                        self._revisions[camera_id] += 1
                except urllib.error.HTTPError as exc:
                    if exc.code == 204:
                        with self._lock:
                            if self._frames[camera_id] is not None:
                                self._frames[camera_id] = None
                                self._revisions[camera_id] += 1
                except Exception:
                    # The telemetry flag controls visibility; transient network
                    # failures retain the last good frame until analysis stops.
                    pass
            delay = max(0.0, 0.125 - (time.monotonic() - started))
            time.sleep(delay)


class Home3DPage(QWidget):
    """Lightweight 3D-only page; rendering details remain in ``depends``."""

    def __init__(self, pi_url, parent=None):
        super().__init__(parent)
        self.pi_url = pi_url
        self.fetcher = None
        self._busy = False
        self._smooth = False
        self._smooth_seconds = 0.5
        self._display_pose = None
        self._last_time = None
        self._trail_visible = False
        self._trail_duration = 30
        self._trail = []  # (timestamp, (x, y, z)); persistent mode must not be sample-capped.
        self._demo_mode = False
        self._demo_state = None
        self._demo_candidate = None
        self._demo_candidate_since = 0.0
        self._demo_camera = None
        self._demo_camera_time = None
        self._demo_light_seen = {"top": 0.0, "bottom": 0.0}
        self._demo_motion_seen = 0.0
        self._demo_state_since = 0.0
        self._demo_feeder_seen = 0.0
        self._demo_placement_order = None
        self._demo_placement_latched = False
        self._demo_home_idle_since = None
        self._vision_preview_revisions = {1: -1, 2: -1}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        if GL_OK:
            self.gl = GLW3D()
            layout.addWidget(self.gl)
            self.refresh_theme()
        else:
            self.gl = None
            label = QLabel("3D view unavailable (install pyqtgraph and PyOpenGL)")
            label.setAlignment(Qt.AlignCenter)
            layout.addWidget(label)
        # Keep the overlay in the GL widget's stacking context so it remains
        # visible above QOpenGLWidget/GLViewWidget on all Qt backends.
        overlay_parent = self.gl if self.gl else self
        self._vision_preview_overlay = QWidget(overlay_parent)
        self._vision_preview_overlay.setAttribute(
            Qt.WA_TransparentForMouseEvents, True
        )
        preview_layout = QVBoxLayout(self._vision_preview_overlay)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(8)
        self._vision_preview_labels = {}
        for camera_id in (1, 2):
            preview = QLabel()
            # The host GUI masks 30 px at the top and bottom of its 320x240
            # camera frame, leaving a 320x180 (16:9) visible viewport.
            preview.setFixedSize(432, 243)
            preview.setAlignment(Qt.AlignCenter)
            preview.setStyleSheet(
                "QLabel { background: #080a0c; border: 1px solid #555b62; }"
            )
            preview.setToolTip(f"Vision Camera {camera_id}")
            preview.hide()
            preview_layout.addWidget(preview)
            self._vision_preview_labels[camera_id] = preview
        self._vision_preview_overlay.adjustSize()
        self._vision_preview_overlay.hide()
        self.preview_fetcher = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(50)
        self._start()

    def refresh_theme(self, background=None):
        """Apply the resolved application background to the 3D viewport."""
        if self.gl:
            if background is None:
                app = QApplication.instance()
                palette = app.palette() if app is not None else self.palette()
                background = palette.color(QPalette.Window)
            self.gl.set_background_color(background)

    def _start(self):
        if self.fetcher:
            self.fetcher.running = False
        self.fetcher = Fetcher(f"{self.pi_url}/api/telemetry", pi_url=self.pi_url)
        self.fetcher.start()
        if self.preview_fetcher:
            self.preview_fetcher.running = False
        self.preview_fetcher = VisionPreviewFetcher(self.pi_url)
        self.preview_fetcher.start()

    def set_cookie(self, cookie):
        if self.fetcher:
            self.fetcher.set_cookie(cookie)
        if self.preview_fetcher:
            self.preview_fetcher.set_cookie(cookie)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_vision_preview()

    def _position_vision_preview(self):
        overlay = getattr(self, "_vision_preview_overlay", None)
        if not overlay:
            return
        overlay.adjustSize()
        parent = overlay.parentWidget() or self
        overlay.move(max(12, parent.width() - overlay.width() - 16), 16)
        overlay.raise_()

    def set_trail_visible(self, visible):
        self._trail_visible = bool(visible)
        if self.gl and GL_BACKEND == "pyqtgraph":
            self.gl.set_trail_visible(self._trail_visible)

    def set_trail_duration(self, seconds):
        self._trail_duration = int(seconds)

    def clear_trail(self):
        self._trail.clear()
        if self.gl:
            self.gl.clear_trail()

    def clear_pcb_modules(self):
        if self.fetcher:
            self.fetcher.clear_pcb_model_cache()
        if self.gl:
            self.gl.set_pcb_model(None, None, None)

    def clear_scan_result(self):
        if self.gl:
            self.gl.set_board_scan(None)

    def set_scene_part_visible(self, part, visible):
        if self.gl:
            self.gl.set_scene_part_visible(part, bool(visible))

    def set_smooth_3d_motion(self, enabled):
        self._smooth = bool(enabled)
        self._display_pose = None
        self._last_time = None

    def set_demo_mode(self, enabled):
        self._demo_mode = bool(enabled)
        self._demo_state = None
        self._demo_candidate = None
        self._demo_candidate_since = 0.0
        self._demo_camera = None
        self._demo_camera_time = None
        self._demo_light_seen = {"top": 0.0, "bottom": 0.0}
        self._demo_motion_seen = 0.0
        self._demo_state_since = 0.0
        self._demo_feeder_seen = 0.0
        self._demo_placement_order = None
        self._demo_placement_latched = False
        self._demo_home_idle_since = None
        if self.gl:
            self.gl.set_demo_mode(self._demo_mode)

    @staticmethod
    def _demo_level(data, primary, fallback):
        try:
            return max(0, int(data.get(primary, data.get(fallback, 0)) or 0))
        except (TypeError, ValueError):
            return 0

    def _demo_context(self, data, pose, feeders, pcb_state, now):
        x, y, z, _h = pose
        velocity = data.get("velocity") or {}
        try:
            xy_speed = math.hypot(
                float(velocity.get("x", 0.0) or 0.0),
                float(velocity.get("y", 0.0) or 0.0),
            )
            z_speed = abs(float(velocity.get("z", 0.0) or 0.0))
        except (TypeError, ValueError):
            xy_speed = z_speed = 0.0

        top_level = self._demo_level(data, "light1", "l1")
        bottom_level = self._demo_level(data, "light2", "l2")
        if top_level > 0:
            self._demo_light_seen["top"] = now
        if bottom_level > 0:
            self._demo_light_seen["bottom"] = now
        # Keep a just-extinguished lamp active briefly so auto-exposure probes
        # do not make the shot jump between the camera and the machine.
        top_active = top_level > 0 or now - self._demo_light_seen["top"] < 0.35
        bottom_active = (
            bottom_level > 0 or now - self._demo_light_seen["bottom"] < 0.35
        )
        raw_moving = xy_speed >= 5.0 or z_speed >= 5.0
        if raw_moving:
            self._demo_motion_seen = now
        moving = raw_moving or now - self._demo_motion_seen < 0.18

        offsets = self.fetcher.get_tool_offsets() if self.fetcher else None
        offsets = offsets or {"pl": (0.0, -12.0), "pr": (0.0, 12.0)}
        balance_z = self.fetcher.get_balance_z() if self.fetcher else 20.0
        dz = float(z) - float(balance_z)
        lower_nozzle = min(offsets, key=lambda key: offsets[key][1])
        raised_nozzle = max(offsets, key=lambda key: offsets[key][1])
        moving_nozzle = lower_nozzle if dz >= 0.0 else raised_nozzle

        held = (pcb_state or {}).get("held_component") or {}
        held_nozzle = str(held.get("nozzle", "") or "").strip().lower()
        if held_nozzle not in offsets:
            held_nozzle = None
        active_nozzle = held_nozzle
        vacuum_engaged = False
        if active_nozzle is None:
            vacuum_active = []
            for key, suffix in (("pl", "1"), ("pr", "2")):
                if data.get(f"valve{suffix}", data.get(f"v{suffix}", 0)) or data.get(
                    f"pump{suffix}", data.get(f"p{suffix}", 0)
                ):
                    vacuum_active.append(key)
            vacuum_engaged = bool(vacuum_active)
            if len(vacuum_active) == 1:
                active_nozzle = vacuum_active[0]
            elif z_speed >= 5.0:
                active_nozzle = moving_nozzle

        nozzle_tips = {}
        for key, (offset_x, offset_y) in offsets.items():
            nozzle_dz = -dz if key == lower_nozzle else dz
            nozzle_tips[key] = (
                x + float(offset_x),
                y + float(offset_y),
                float(balance_z) + nozzle_dz,
            )

        bottom = self.fetcher.get_visit_2cam() if self.fetcher else None
        nearest_feeder = min(
            (
                (math.hypot(x - pos[0], y - pos[1]), key, pos)
                for key, pos in (feeders or {}).items()
            ),
            default=None,
        )
        feeder_distance = nearest_feeder[0] if nearest_feeder else math.inf
        if feeder_distance <= 32.0:
            self._demo_feeder_seen = now
        in_feeder = bool(
            feeder_distance <= 32.0
            or now - self._demo_feeder_seen < 0.30
        )
        in_work = x >= 105.0 and 45.0 <= y <= 230.0
        pcb_center = (pcb_state or {}).get("center_jp") or {}
        try:
            in_work = in_work or math.hypot(
                x - float(pcb_center["x"]), y - float(pcb_center["y"])
            ) <= 95.0
        except (KeyError, TypeError, ValueError):
            pass

        workflow = data.get("workflow")
        if isinstance(workflow, dict) and "state" in workflow:
            workflow_state = str(workflow.get("state", "idle") or "idle").lower()
            workflow_order = str(workflow.get("order_id", "") or "").upper()
            placement_active = (
                workflow_state in ("running", "paused")
                and not workflow_order.startswith("CAL_")
            )
        else:
            # Compatibility with Host versions that do not publish workflow.
            # Latch on the first real placement action and release when every
            # tracked component is finished or the stopped machine returns home.
            model_state = pcb_state or {}
            order_id = str(model_state.get("order_id", "") or "").upper()
            completed = {
                str(value).strip().upper()
                for value in model_state.get("completed_designators", [])
            }
            failed = {
                str(value).strip().upper()
                for value in model_state.get("failed_designators", [])
            }
            materials = {
                str(value).strip().upper()
                for value in (model_state.get("component_materials") or {})
            }
            if not materials:
                materials = {
                    str(value).strip().upper()
                    for value in model_state.get("visible_designators", [])
                }
            finished = completed | failed
            task_complete = bool(materials) and materials <= finished
            io_active = bool(
                held_nozzle
                or data.get("valve1", data.get("v1", 0))
                or data.get("valve2", data.get("v2", 0))
                or data.get("pump1", data.get("p1", 0))
                or data.get("pump2", data.get("p2", 0))
            )
            progress_seen = bool(
                finished
                or model_state.get("released_components")
                or model_state.get("pick_inspections")
            )
            if order_id != self._demo_placement_order:
                self._demo_placement_order = order_id
                self._demo_placement_latched = bool(
                    order_id and not task_complete and (io_active or progress_seen)
                )
                self._demo_home_idle_since = None
            elif not order_id or not model_state.get("active") or task_complete:
                self._demo_placement_latched = False
                self._demo_home_idle_since = None
            elif io_active:
                self._demo_placement_latched = True
                self._demo_home_idle_since = None
            elif progress_seen:
                self._demo_placement_latched = True

            home_idle = (
                self._demo_placement_latched
                and math.hypot(x, y) <= 30.0
                and not raw_moving
                and not io_active
                and not held_nozzle
                and top_level <= 0
                and bottom_level <= 0
            )
            if home_idle:
                if self._demo_home_idle_since is None:
                    self._demo_home_idle_since = now
                elif now - self._demo_home_idle_since >= 2.0:
                    self._demo_placement_latched = False
            else:
                self._demo_home_idle_since = None
            placement_active = self._demo_placement_latched

        if top_active or bottom_active:
            if top_active and bottom_active:
                bottom_distance = (
                    math.hypot(x - bottom[0], y - bottom[1]) if bottom else math.inf
                )
                camera = "bottom" if bottom_distance <= 35.0 else "top"
            else:
                camera = "top" if top_active else "bottom"
            state = f"{camera}_camera"
        elif active_nozzle and (z_speed >= 5.0 or vacuum_engaged):
            state = "nozzle_move" if xy_speed >= 5.0 else "nozzle"
        elif held_nozzle:
            state = "nozzle_move" if xy_speed >= 5.0 else "nozzle"
        elif xy_speed >= 5.0:
            state = "movement"
        elif in_feeder:
            state = "feeder"
        elif in_work:
            state = "placement"
        elif math.hypot(x, y) <= 30.0:
            state = "overview"
        else:
            state = "default"

        return {
            "state": state,
            "moving": moving,
            "in_feeder": in_feeder,
            "in_work": in_work,
            "placement_active": placement_active,
            "pose": pose,
            "active_nozzle": active_nozzle,
            "nozzle_tips": nozzle_tips,
            "bottom": bottom,
            "nearest_feeder": nearest_feeder,
            "pcb_state": pcb_state or {},
            "top_preview_visible": not self._vision_preview_labels[1].isHidden(),
        }

    def _demo_target(self, state, context):
        x, y, _z, _h = context["pose"]
        nozzle = context["active_nozzle"]
        tip = context["nozzle_tips"].get(nozzle, (x, y, 12.0))

        def global_center(target_x, target_y, z=14.0, weight=0.42):
            # Wide shots keep a stable work-area anchor and only partially
            # follow the gantry. This avoids sweeping the camera across the
            # complete machine for every long XY move.
            anchor_x, anchor_y = 155.0, 125.0
            return (
                anchor_x + (float(target_x) - anchor_x) * weight,
                anchor_y + (float(target_y) - anchor_y) * weight,
                float(z),
            )

        # Keep the complete camera housing in frame. The previous 62.5 scene
        # units were inside the housing, so the close-up showed no useful view.
        default_distance = 360.0
        moving_distance = 240.0
        close_distance = 180.0
        if state == "top_camera":
            if context["moving"]:
                distance = close_distance
            else:
                distance = 80.0 if context["in_feeder"] else 60.0
            return ((x, y, 20.0), distance, 24.0, -45.0, "top_camera")
        if state == "bottom_camera":
            bottom = context["bottom"] or (x, y)
            # Aim just above the upward-looking lens. At this distance the
            # working nozzle remains in frame instead of being hidden.
            return (
                (float(bottom[0]), float(bottom[1]), 8.0),
                close_distance * 1.15,
                22.0,
                -42.0,
                "bottom_camera",
            )
        if state == "nozzle":
            distance = 60.0 if (
                context["in_work"] or context["in_feeder"]
            ) else close_distance
            return (tip, distance, 22.0, -42.0, "nozzle")
        if state == "nozzle_move":
            return (tip, moving_distance, 30.0, -45.0, "nozzle")
        if state == "movement":
            return (
                global_center(x, y),
                default_distance,
                34.0,
                -45.0,
                "machine",
            )
        if state == "feeder":
            nearest = context["nearest_feeder"]
            center = nearest[2] if nearest else (x, y)
            return (
                global_center(center[0], center[1], 10.0, 0.58),
                default_distance,
                34.0,
                -45.0,
                "feeder",
            )
        if state == "placement":
            pcb_center = context["pcb_state"].get("center_jp") or {}
            try:
                center = (
                    (x + float(pcb_center["x"])) * 0.5,
                    (y + float(pcb_center["y"])) * 0.5,
                    10.0,
                )
            except (KeyError, TypeError, ValueError):
                center = (x, y, 10.0)
            return (center, default_distance, 38.0, -50.0, "workdesk")
        if state == "overview":
            return ((155.0, 125.0, 18.0), 430.0, 32.0, 45.0, "overview")
        return (global_center(x, y), default_distance, 36.0, -45.0, "machine")

    @staticmethod
    def _demo_visibility(context, subject):
        """Keep only the machine group needed for the current shot visible."""
        visibility = {
            "pick_top_camera": False,
            "bottom_camera": False,
            "feeders": False,
            "workdesk": True,
        }
        if subject == "overview":
            visibility = {key: True for key in visibility}
        elif subject == "top_camera":
            if context.get("in_feeder"):
                visibility["feeders"] = True
            else:
                visibility["workdesk"] = True
        elif subject == "bottom_camera":
            visibility.update(
                pick_top_camera=True,
                bottom_camera=True,
                workdesk=True,
            )
        elif subject in ("nozzle", "machine"):
            visibility.update(pick_top_camera=True, workdesk=True)
            if context.get("nearest_feeder"):
                visibility["feeders"] = True
        elif subject == "nozzle_move":
            visibility.update(pick_top_camera=True, workdesk=True)
        elif subject == "feeder":
            visibility.update(pick_top_camera=True, feeders=True)
        elif subject == "placement":
            visibility.update(pick_top_camera=True, workdesk=True)
        elif subject == "movement":
            visibility.update(pick_top_camera=True, workdesk=True)
        # The real top-camera preview alone controls this model group.
        visibility["pick_top_camera"] = not bool(
            context.get("top_preview_visible")
        )
        return visibility

    def _update_demo_camera(self, data, pose, feeders, pcb_state, now):
        if not self._demo_mode:
            return
        context = self._demo_context(data, pose, feeders, pcb_state, now)
        candidate = context["state"]
        if candidate != self._demo_candidate:
            self._demo_candidate = candidate
            self._demo_candidate_since = now
        priority_state = candidate in ("top_camera", "bottom_camera", "nozzle")
        settle_seconds = 0.08 if priority_state else 0.20
        if self._demo_state is None or (
            candidate != self._demo_state
            and now - self._demo_candidate_since >= settle_seconds
            and (
                priority_state
                or now - self._demo_state_since >= 0.25
            )
        ):
            self._demo_state = candidate
            self._demo_state_since = now

        target = self._demo_target(self._demo_state, context)
        self.gl.set_demo_scene_visibility(self._demo_visibility(context, target[4]))
        self.gl.set_demo_scene_opacity(
            {
                "feeders": 0.50 if context["placement_active"] else 1.0,
                "feeder_contents": 1.0,
            }
        )
        target_center = tuple(target[0])
        target_camera = target_center + tuple(target[1:4])
        if self._demo_camera is None or self._demo_camera_time is None:
            self._demo_camera = target_camera
        else:
            elapsed = max(0.0, now - self._demo_camera_time)
            focus_alpha = 1.0 - math.exp(-elapsed / 0.45)
            zoom_alpha = 1.0 - math.exp(-elapsed / 0.55)
            angle_alpha = 1.0 - math.exp(-elapsed / 0.70)
            old_center = self._demo_camera[:3]
            next_center = [
                old + (new - old) * focus_alpha
                for old, new in zip(old_center, target_camera[:3])
            ]
            focus_step = math.dist(old_center, next_center)
            max_focus_step = max(0.35, elapsed * 140.0)
            if focus_step > max_focus_step:
                scale = max_focus_step / focus_step
                next_center = [
                    old + (new - old) * scale
                    for old, new in zip(old_center, next_center)
                ]
            values = next_center
            values.append(
                self._demo_camera[3]
                + (target_camera[3] - self._demo_camera[3]) * zoom_alpha
            )
            values.append(
                self._demo_camera[4]
                + (target_camera[4] - self._demo_camera[4]) * angle_alpha
            )
            angle_delta = (
                target_camera[5] - self._demo_camera[5] + 180.0
            ) % 360.0 - 180.0
            values.append(self._demo_camera[5] + angle_delta * angle_alpha)
            self._demo_camera = tuple(values)
        self._demo_camera_time = now
        self.gl.set_demo_camera(
            center=self._demo_camera[:3],
            distance=self._demo_camera[3],
            elevation=self._demo_camera[4],
            azimuth=self._demo_camera[5],
        )

    def _pose(self, x, y, z, h, now):
        target = (
            float(x or 0),
            float(y or 0),
            float(z or 0),
            float(h or 0),
        )
        if not self._smooth or self._display_pose is None or self._last_time is None:
            self._display_pose, self._last_time = target, now
            return target
        alpha = 1.0 - math.exp(-max(0.0, now - self._last_time) / self._smooth_seconds)
        self._last_time = now
        self._display_pose = tuple(a + (b - a) * alpha for a, b in zip(self._display_pose, target))
        return self._display_pose

    def _update_vision_previews(self, status):
        status = status or {}
        status_has_activity = any(
            f"cam{camera_id}" in status for camera_id in (1, 2)
        )
        visible = False
        for camera_id in (1, 2):
            label = self._vision_preview_labels[camera_id]
            raw, revision = self.preview_fetcher.get_frame(camera_id)
            active = bool(
                raw
                and (
                    not status_has_activity
                    or bool((status.get(f"cam{camera_id}") or {}).get("active"))
                )
            )
            if not active:
                if label.isVisible():
                    label.clear()
                    label.hide()
                continue

            if raw and revision != self._vision_preview_revisions[camera_id]:
                image = QImage.fromData(raw, "JPG")
                if not image.isNull():
                    pixmap = QPixmap.fromImage(image).scaled(
                        label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                    label.setPixmap(pixmap)
                    label.show()
                    self._vision_preview_revisions[camera_id] = revision
            # isVisible() is false while the parent overlay is hidden, even
            # after label.show(); use the widget's explicit hidden state.
            visible = visible or not label.isHidden()

        self._vision_preview_overlay.setVisible(visible)
        if visible:
            self._position_vision_preview()

    def _tick(self):
        if self._busy or not self.gl or not self.fetcher:
            return
        self._busy = True
        try:
            data = self.fetcher.get()
            if not data:
                return
            self._update_vision_previews(data.get("vision_preview"))
            pos = data.get("position") or {}
            now = time.time()
            pose = self._pose(
                pos.get("x"), pos.get("y"), pos.get("z"), pos.get("h"), now
            )
            display_x, display_y, display_z, display_h = pose
            if not self._trail or any(
                abs(pose[index] - self._trail[-1][1][index]) > 0.001
                for index in range(3)
            ):
                self._trail.append((now, (display_x, display_y, display_z)))
            trail = []
            if self._trail_visible:
                samples = self._trail
                if self._trail_duration > 0:
                    cutoff = now - self._trail_duration
                    samples = [sample for sample in samples if sample[0] >= cutoff]
                trail = [sample[1] for sample in samples]
            offsets = self.fetcher.get_tool_offsets()
            feeders, active = self.fetcher.get_feeders()
            feeder_inventory, component_scale = self.fetcher.get_feeder_inventory()
            display_h_scene = display_h * self.fetcher.get_h_scene_scale()
            pcb_state, pcb_data, pcb_preview = self.fetcher.get_pcb_model()
            self.gl.set_tool_offsets(offsets)
            self.gl.set_bottom_camera_origin(self.fetcher.get_visit_2cam())
            self.gl.set_feeders(feeders, active)
            self.gl.set_feeder_components(feeder_inventory, component_scale)
            self.gl.set_board_scan(data.get("board_scan"))
            self.gl.set_pcb_model(pcb_state, pcb_data, pcb_preview)
            self.gl.set_ring_light_levels(data.get("light1", data.get("l1", 0)), data.get("light2", data.get("l2", 0)))
            if GL_BACKEND == "pyqtgraph":
                self.gl.set_pose(
                    display_x,
                    display_y,
                    display_z,
                    trail=trail,
                    balance_z=self.fetcher.get_balance_z(),
                    h=display_h_scene,
                )
            else:
                self.gl.set_pose(
                    display_x,
                    display_y,
                    display_z,
                    trail=trail,
                    show_trail=bool(trail),
                    balance_z=self.fetcher.get_balance_z(),
                    h=display_h_scene,
                )
            self._update_demo_camera(data, pose, feeders, pcb_state, now)
        finally:
            self._busy = False

    def stop(self):
        self.timer.stop()
        if self.fetcher:
            self.fetcher.running = False
        if self.preview_fetcher:
            self.preview_fetcher.running = False
