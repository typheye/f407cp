"""Legacy QGL implementation for the JanPNP 3D preview."""
from __future__ import annotations

try:
    from . import preview as _preview_context
except ImportError:
    import preview as _preview_context

globals().update(
    {
        name: value
        for name, value in vars(_preview_context).items()
        if not name.startswith("__")
    }
)
if True:
    class GLW3D(QGLWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.x = 0.0; self.y = 0.0; self.z = 0.0
            self.h = 0.0
            self.trail = []
            self._tool_offsets = None
            self._bottom_camera_origin = None
            self._feeder_origins = dict(DEFAULT_FEEDERS_ORIGIN)
            self._active_feeders = set(DEFAULT_FEEDERS_ORIGIN.keys())
            self._feeder_inventory = []
            self._component_scale = {"x": 1.0, "y": 1.0}
            self._pcb_model_state = None
            self._pcb_model_data = None
            self._pcb_model_preview = None
            self._board_scan_state = None
            self._ring_light_levels = {"top": 0, "bottom": 0}
            self._display_visibility = {
                "pick_top_camera": True,
                "bottom_camera": True,
                "feeders": True,
                "workdesk": True,
            }
            self._demo_mode = False
            self._demo_center = None
            self._demo_saved_camera = None
            self._demo_saved_visibility = None
            self._demo_emphasis = ("overview", None)
            self._demo_part_opacity = {}
            self._background_color = QColor(13, 15, 18)
            self.balance_z = DEFAULT_BALANCE_Z
            self.cam_yaw = 45.0; self.cam_pitch = 35.0; self.cam_distance = 420.0
            self.last_mouse_x = 0; self.last_mouse_y = 0; self.dragging = False
            self.setMinimumSize(480, 320)
            self.setMouseTracking(True)
            # Original locating vertices; drawing uses expanded copies only.
            self._board_anchor_verts = [
                (143.38, 72.48, 0.0), (274.17, 72.70, 0.0),
                (274.65, 201.97, 0.0), (143.68, 202.02, 0.0),
                (143.38, 72.48, BOARD_TOP_Z), (274.17, 72.70, BOARD_TOP_Z),
                (274.65, 201.97, BOARD_TOP_Z), (143.68, 202.02, BOARD_TOP_Z),
            ]
            anchor_top = np.array(self._board_anchor_verts[4:8], dtype=float)
            min_x = float(anchor_top[:, 0].min())
            max_x = float(anchor_top[:, 0].max())
            min_y = float(anchor_top[:, 1].min())
            max_y = float(anchor_top[:, 1].max())
            board_w = max_x - min_x
            board_d = max_y - min_y
            board_center_x = (min_x + max_x) / 2.0
            board_center_y = (min_y + max_y) / 2.0
            verts, _faces = _mesh_box(board_w, board_d, BOARD_TOP_Z)
            verts[:, 0] += board_center_x
            verts[:, 1] += board_center_y
            self._board_verts = [tuple(p) for p in verts]
            self._workdesk_bounds_signature = None

        def set_background_color(self, color):
            """Match the OpenGL viewport to the active Qt window palette."""
            self._background_color = QColor(color)
            super().update()

        def set_demo_mode(self, enabled):
            enabled = bool(enabled)
            if enabled == self._demo_mode:
                return
            if enabled:
                self._demo_saved_camera = (
                    self.cam_yaw, self.cam_pitch, self.cam_distance
                )
                self._demo_saved_visibility = dict(self._display_visibility)
            self._demo_mode = enabled
            self.dragging = False
            if not enabled:
                self._demo_emphasis = ("overview", None)
                self._demo_part_opacity = {}
                if self._demo_saved_camera:
                    self.cam_yaw, self.cam_pitch, self.cam_distance = (
                        self._demo_saved_camera
                    )
                for part, visible in (self._demo_saved_visibility or {}).items():
                    self.set_scene_part_visible(part, visible)
                self._demo_center = None
                self._demo_saved_camera = None
                self._demo_saved_visibility = None
            super().update()

        def set_demo_scene_visibility(self, visibility):
            if not self._demo_mode:
                return
            for part, visible in (visibility or {}).items():
                visible = bool(visible)
                if self._display_visibility.get(part) != visible:
                    self.set_scene_part_visible(part, visible)

        def set_demo_scene_opacity(self, opacity):
            if not self._demo_mode:
                return
            next_opacity = {
                "feeder": max(
                    0.0, min(1.0, float((opacity or {}).get("feeders", 1.0)))
                ),
                "feeder_content": max(
                    0.0,
                    min(
                        1.0,
                        float((opacity or {}).get("feeder_contents", 1.0)),
                    ),
                ),
            }
            if next_opacity == self._demo_part_opacity:
                return
            self._demo_part_opacity = next_opacity
            super().update()

        @staticmethod
        def _demo_group_opacity(subject, group, nozzle=None, active_nozzle=None):
            if subject == "overview":
                return 1.0
            if subject == "top_camera":
                return 1.0 if group == "top_camera" else 0.30
            if subject == "bottom_camera":
                if group == "bottom_camera" or (
                    group == "nozzle" and nozzle == active_nozzle
                ):
                    return 1.0
                if group in ("head_frame", "top_camera"):
                    return 0.70
                return 0.30
            if subject == "nozzle":
                if group == "nozzle" and nozzle == active_nozzle:
                    return 1.0
                if group in ("top_camera", "head_frame", "nozzle"):
                    return 0.70
                return 0.30
            if subject == group:
                return 1.0
            if subject == "machine" and group in (
                "top_camera", "head_frame", "nozzle"
            ):
                return 1.0
            return 0.30

        def set_demo_scene_emphasis(self, subject, active_nozzle=None):
            if not self._demo_mode:
                return
            self._demo_emphasis = (
                str(subject or "overview"),
                str(active_nozzle or "").lower() or None,
            )
            super().update()

        def _demo_opacity(self, group, nozzle=None):
            if not self._demo_mode:
                return 1.0
            emphasis = self._demo_group_opacity(
                self._demo_emphasis[0],
                group,
                nozzle,
                self._demo_emphasis[1],
            )
            return emphasis * self._demo_part_opacity.get(group, 1.0)

        @staticmethod
        def _faded_color(color, opacity):
            rgba = list(color)
            while len(rgba) < 4:
                rgba.append(1.0)
            rgba[3] = float(rgba[3]) * float(opacity)
            return tuple(rgba[:4])

        @staticmethod
        def _set_transparency(opacity):
            if opacity < 0.999:
                glEnable(GL_BLEND)
                glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
                glDepthMask(GL_FALSE)
            else:
                glDisable(GL_BLEND)
                glDepthMask(GL_TRUE)

        def set_demo_camera(self, center, distance, elevation, azimuth):
            self._demo_center = tuple(float(value) for value in center)
            self.cam_distance = float(distance)
            self.cam_pitch = float(elevation)
            self.cam_yaw = float(azimuth)
            super().update()

        def set_pose(self, x, y, z, trail, show_trail=False, balance_z=DEFAULT_BALANCE_Z, h=0.0):
            self.x = float(x or 0.0); self.y = float(y or 0.0); self.z = float(z or 0.0)
            self.h = float(h or 0.0)
            self.balance_z = float(balance_z)
            self.trail = list(trail)
            self._show_trail = show_trail and len(self.trail) >= 2
            super().update()

        def clear_trail(self):
            self.trail.clear()
            self._show_trail = False
            super().update()

        def set_tool_offsets(self, offsets):
            if offsets:
                self._tool_offsets = {
                    "pl": (float(offsets["pl"][0]), float(offsets["pl"][1])),
                    "pr": (float(offsets["pr"][0]), float(offsets["pr"][1])),
                }
                super().update()

        def set_bottom_camera_origin(self, origin):
            if origin:
                self._bottom_camera_origin = (float(origin[0]), float(origin[1]), 0.0)
                super().update()

        def set_feeders(self, origins, active_keys):
            self._feeder_origins = dict(origins or {})
            self._active_feeders = set(active_keys or [])
            super().update()

        def set_pcb_model(self, state, model, preview=None):
            self._pcb_model_state = dict(state) if state and state.get("active") else None
            self._pcb_model_data = dict(model) if self._pcb_model_state and model else None
            self._pcb_model_preview = preview if self._pcb_model_state is not None else None
            super().update()

        def set_feeder_components(self, inventory, scale=None):
            self._feeder_inventory = [dict(item) for item in (inventory or [])]
            scale = scale or {}
            self._component_scale = {
                "x": abs(float(scale.get("x", 1.0) or 1.0)),
                "y": abs(float(scale.get("y", 1.0) or 1.0)),
            }
            super().update()

        def set_ring_light_levels(self, top_level=0, bottom_level=0):
            self._ring_light_levels = {
                "top": max(0, min(100, int(top_level or 0))),
                "bottom": max(0, min(100, int(bottom_level or 0))),
            }
            super().update()

        def set_scene_part_visible(self, part, visible):
            if part in self._display_visibility:
                self._display_visibility[part] = bool(visible)
                super().update()

        def set_board_scan(self, state):
            self._board_scan_state = dict(state) if state else None
            bounds = (state or {}).get("mosaic_bounds_jp") or {}
            try:
                signature = tuple(
                    round(float(bounds[key]), 4)
                    for key in ("x_min", "x_max", "y_min", "y_max")
                )
                if signature != self._workdesk_bounds_signature:
                    min_x, max_x, min_y, max_y = signature
                    verts, _faces = _mesh_box(
                        max_x - min_x, max_y - min_y, BOARD_TOP_Z
                    )
                    verts[:, 0] += (min_x + max_x) * 0.5
                    verts[:, 1] += (min_y + max_y) * 0.5
                    self._board_verts = [tuple(point) for point in verts]
                    self._workdesk_bounds_signature = signature
            except (KeyError, TypeError, ValueError):
                pass
            super().update()

        def initializeGL(self):
            glEnable(GL_DEPTH_TEST)
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            glPointSize(8.0)

        def resizeGL(self, w, h):
            h = max(1, h)
            glViewport(0, 0, w, h)
            glMatrixMode(GL_PROJECTION)
            glLoadIdentity()
            gluPerspective(45.0, float(w) / float(h), 1.0, 2000.0)
            glMatrixMode(GL_MODELVIEW)

        def mousePressEvent(self, event):
            if self._demo_mode:
                event.accept()
                return
            if event.button() == Qt.LeftButton:
                self.dragging = True
                self.last_mouse_x = event.x(); self.last_mouse_y = event.y()

        def mouseReleaseEvent(self, event):
            if self._demo_mode:
                event.accept()
                return
            if event.button() == Qt.LeftButton:
                self.dragging = False

        def mouseMoveEvent(self, event):
            if self._demo_mode:
                event.accept()
                return
            if self.dragging:
                self.cam_yaw += (event.x() - self.last_mouse_x) * 0.4
                self.cam_pitch += (event.y() - self.last_mouse_y) * 0.4
                self.cam_pitch = max(10.0, min(80.0, self.cam_pitch))
                self.last_mouse_x = event.x(); self.last_mouse_y = event.y()
                super().update()

        def wheelEvent(self, event):
            if self._demo_mode:
                event.accept()
                return
            self.cam_distance -= event.angleDelta().y() * 0.25
            self.cam_distance = max(80.0, min(900.0, self.cam_distance))
            super().update()

        def keyPressEvent(self, event):
            if self._demo_mode:
                event.accept()
                return
            super().keyPressEvent(event)

        def keyReleaseEvent(self, event):
            if self._demo_mode:
                event.accept()
                return
            super().keyReleaseEvent(event)

        def _draw_grid(self):
            glColor4f(0.35, 0.38, 0.40, 0.45)
            glBegin(GL_LINES)
            for i in range(-10, 11):
                v = i * 20.0
                glVertex3f(-220.0, v, 0.0); glVertex3f(220.0, v, 0.0)
                glVertex3f(v, -220.0, 0.0); glVertex3f(v, 220.0, 0.0)
            glEnd()

        def _draw_axes(self):
            # Red X-axis (forward)
            glLineWidth(3.0)
            glColor4f(1.0, 0.08, 0.08, 0.9)
            glBegin(GL_LINES)
            glVertex3f(0.0, 0.0, 0.0); glVertex3f(280.0, 0.0, 0.0)
            glEnd()
            # Green Y-axis (right)
            glColor4f(0.08, 1.0, 0.08, 0.9)
            glBegin(GL_LINES)
            glVertex3f(0.0, 0.0, 0.0); glVertex3f(0.0, 280.0, 0.0)
            glEnd()
            # White origin dot
            glLineWidth(1.0)
            glPointSize(8.0)
            glColor4f(1.0, 1.0, 1.0, 0.8)
            glBegin(GL_POINTS)
            glVertex3f(0.0, 0.0, 0.0)
            glEnd()

        def paintGL(self):
            color = self._background_color
            glClearColor(color.redF(), color.greenF(), color.blueF(), 1.0)
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
            glLoadIdentity()
            target = self._demo_center if self._demo_mode and self._demo_center else (
                self.x, self.y, self.z
            )
            tx, ty, tz = target
            cx = tx + self.cam_distance * math.sin(math.radians(self.cam_yaw)) * math.cos(math.radians(self.cam_pitch))
            cy = ty + self.cam_distance * math.cos(math.radians(self.cam_yaw)) * math.cos(math.radians(self.cam_pitch))
            cz = tz + self.cam_distance * math.sin(math.radians(self.cam_pitch))
            gluLookAt(cx, cy, cz, tx, ty, tz, 0.0, 0.0, 1.0)
            # Base environment grid hidden; keep board grid and axes only.
            self._draw_axes()
            if self._display_visibility["workdesk"]:
                self._draw_board()
                self._draw_board_scan()
            self._draw_pcb_model()
            if self._display_visibility["feeders"]:
                self._draw_feeders()
                self._draw_feeder_components()
            self._draw_machine_model()
            if self._show_trail:
                glDisable(GL_DEPTH_TEST)
                glColor4f(1.0, 0.55, 0.12, 1.0)
                glBegin(GL_LINE_STRIP)
                for px, py, pz in self.trail:
                    glVertex3f(float(px), float(py), float(pz))
                glEnd()
                glEnable(GL_DEPTH_TEST)
            # Red machine origin is drawn as a sphere in _draw_machine_model().

        def _draw_board_scan(self):
            state = self._board_scan_state or {}
            # The fitted outline is used for positioning, but the live view
            # intentionally shows only the stitched scan texture and PCB model.
            return

        def _draw_cylinder(self, x, y, z, radius, height):
            quad = gluNewQuadric()
            try:
                glPushMatrix()
                glTranslatef(float(x), float(y), float(z))
                gluCylinder(quad, radius, radius, height, 32, 1)
                gluDisk(quad, 0.0, radius, 32, 1)
                glTranslatef(0.0, 0.0, height)
                gluDisk(quad, 0.0, radius, 32, 1)
                glPopMatrix()
            finally:
                gluDeleteQuadric(quad)

        def _draw_ring_cylinder(
            self,
            x,
            y,
            z,
            inner_radius,
            outer_radius,
            height,
            cols=48,
            start_deg=0.0,
            end_deg=360.0,
        ):
            glPushMatrix()
            glTranslatef(float(x), float(y), float(z))
            try:
                span = float(end_deg) - float(start_deg)
                full = abs(span) >= 359.9
                steps = cols if full else max(2, int(round(cols * abs(span) / 360.0)))

                def point(angle, radius, z0):
                    radians = math.radians(angle)
                    return (
                        math.cos(radians) * radius,
                        math.sin(radians) * radius,
                        z0,
                    )

                for z0, z1, r0, r1 in (
                    (0.0, height, outer_radius, outer_radius),
                    (height, 0.0, inner_radius, inner_radius),
                ):
                    glBegin(GL_QUAD_STRIP)
                    for i in range(steps + 1):
                        ratio = i / steps
                        angle = (
                            float(start_deg) + span * ratio
                            if not full
                            else 360.0 * ratio
                        )
                        glVertex3f(*point(angle, r0, z0))
                        glVertex3f(*point(angle, r1, z1))
                    glEnd()
                for zc in (0.0, height):
                    glBegin(GL_QUAD_STRIP)
                    for i in range(steps + 1):
                        ratio = i / steps
                        angle = (
                            float(start_deg) + span * ratio
                            if not full
                            else 360.0 * ratio
                        )
                        glVertex3f(*point(angle, outer_radius, zc))
                        glVertex3f(*point(angle, inner_radius, zc))
                    glEnd()
                if not full:
                    for angle in (float(start_deg), float(end_deg)):
                        glBegin(GL_QUADS)
                        glVertex3f(*point(angle, outer_radius, 0.0))
                        glVertex3f(*point(angle, inner_radius, 0.0))
                        glVertex3f(*point(angle, inner_radius, height))
                        glVertex3f(*point(angle, outer_radius, height))
                        glEnd()
            finally:
                glPopMatrix()

        def _draw_flipped_cylinder(self, x, y, z, radius, height):
            quad = gluNewQuadric()
            try:
                glPushMatrix()
                glTranslatef(float(x), float(y), float(z))
                glRotatef(180.0, 1.0, 0.0, 0.0)
                gluCylinder(quad, radius, radius, height, 32, 1)
                gluDisk(quad, 0.0, radius, 32, 1)
                glTranslatef(0.0, 0.0, height)
                gluDisk(quad, 0.0, radius, 32, 1)
                glPopMatrix()
            finally:
                gluDeleteQuadric(quad)

        def _draw_flipped_ring_cylinder(self, x, y, z, inner_radius, outer_radius, height):
            glPushMatrix()
            glTranslatef(float(x), float(y), float(z))
            glRotatef(180.0, 1.0, 0.0, 0.0)
            try:
                self._draw_ring_cylinder(0.0, 0.0, 0.0, inner_radius, outer_radius, height)
            finally:
                glPopMatrix()

        def _draw_ring_light_glow(self, x, y, anchor_z, level, direction):
            level = max(0, min(100, int(level or 0)))
            if level <= 0:
                return
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE)
            glDepthMask(GL_FALSE)
            active_layers = max(
                1,
                min(
                    RING_LIGHT_GLOW_LAYERS,
                    int(math.ceil(level / (100.0 / RING_LIGHT_GLOW_LAYERS))),
                ),
            )
            alpha_scale = math.pow(level / 100.0, 0.55)
            for idx in range(active_layers):
                layer_fade = 1.0 - (idx / max(1, RING_LIGHT_GLOW_LAYERS))
                alpha = RING_LIGHT_GLOW_MIN_ALPHA + (
                    (RING_LIGHT_GLOW_MAX_ALPHA - RING_LIGHT_GLOW_MIN_ALPHA)
                    * alpha_scale
                    * layer_fade
                )
                alpha *= self._demo_opacity(
                    "top_camera" if direction < 0 else "bottom_camera"
                )
                glColor4f(
                    RING_LIGHT_GLOW_COLOR[0],
                    RING_LIGHT_GLOW_COLOR[1],
                    RING_LIGHT_GLOW_COLOR[2],
                    alpha,
                )
                inner_radius = RING_LIGHT_GLOW_INNER_RADIUS + idx * (RING_LIGHT_GLOW_RADIUS_STEP * 0.45)
                outer_radius = RING_LIGHT_GLOW_OUTER_RADIUS + idx * RING_LIGHT_GLOW_RADIUS_STEP
                z0 = anchor_z + direction * ((idx + 1) * RING_LIGHT_GLOW_STEP)
                if direction < 0:
                    self._draw_flipped_ring_cylinder(
                        x, y, z0, inner_radius, outer_radius, RING_LIGHT_GLOW_HEIGHT
                    )
                else:
                    self._draw_ring_cylinder(
                        x, y, z0, inner_radius, outer_radius, RING_LIGHT_GLOW_HEIGHT
                    )
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            glDepthMask(GL_TRUE)

        def _draw_flipped_box(self, x, y, z, width, depth, height):
            self._draw_box(x, y, z - height, width, depth, height)

        def _draw_sphere(self, x, y, z, radius):
            quad = gluNewQuadric()
            try:
                glPushMatrix()
                glTranslatef(float(x), float(y), float(z))
                gluSphere(quad, radius, 24, 16)
                glPopMatrix()
            finally:
                gluDeleteQuadric(quad)

        def _draw_triangle_mesh(self, verts, faces):
            glBegin(GL_TRIANGLES)
            for a, b, c in faces:
                glVertex3f(*verts[a])
                glVertex3f(*verts[b])
                glVertex3f(*verts[c])
            glEnd()

        def _draw_component_meshes(
            self,
            package,
            x,
            y,
            base_z,
            scale_x,
            scale_y,
            value=None,
            angle=0.0,
            color_boost=1.0,
            alpha=1.0,
        ):
            for vertices, faces, color in build_component_meshes(
                package,
                scale_x,
                scale_y,
                value=value,
                rotation_degrees=angle,
            ):
                vertices = np.asarray(vertices, dtype=float).copy()
                vertices[:, 0] += float(x)
                vertices[:, 1] += float(y)
                vertices[:, 2] += float(base_z)
                draw_color = (
                    _boost_color(color, color_boost)
                    if color_boost != 1.0
                    else color
                )
                glColor4f(
                    float(draw_color[0]),
                    float(draw_color[1]),
                    float(draw_color[2]),
                    float(draw_color[3]) * float(alpha),
                )
                self._draw_triangle_mesh(vertices, faces)

        def _draw_box(self, x, y, z, width, depth, height):
            hx = width / 2.0
            hy = depth / 2.0
            verts = [
                (x - hx, y - hy, z),
                (x + hx, y - hy, z),
                (x + hx, y + hy, z),
                (x - hx, y + hy, z),
                (x - hx, y - hy, z + height),
                (x + hx, y - hy, z + height),
                (x + hx, y + hy, z + height),
                (x - hx, y + hy, z + height),
            ]
            quads = [
                (0, 1, 2, 3),
                (4, 5, 6, 7),
                (0, 1, 5, 4),
                (1, 2, 6, 5),
                (2, 3, 7, 6),
                (3, 0, 4, 7),
            ]
            glBegin(GL_QUADS)
            for i0, i1, i2, i3 in quads:
                glVertex3f(*verts[i0])
                glVertex3f(*verts[i1])
                glVertex3f(*verts[i2])
                glVertex3f(*verts[i3])
            glEnd()

        def _draw_inverted_cone(self, x, y, z, radius, height):
            quad = gluNewQuadric()
            try:
                glPushMatrix()
                glTranslatef(float(x), float(y), float(z))
                glRotatef(180.0, 1.0, 0.0, 0.0)
                gluCylinder(quad, radius, 0.0, height, 32, 1)
                gluDisk(quad, 0.0, radius, 32, 1)
                glPopMatrix()
            finally:
                gluDeleteQuadric(quad)

        def _draw_machine_model(self):
            show_top = self._display_visibility["pick_top_camera"]
            show_bottom = self._display_visibility["bottom_camera"]
            if not show_top:
                if show_bottom and self._bottom_camera_origin:
                    self._draw_bottom_camera()
                return
            top_alpha = self._demo_opacity("top_camera")
            self._set_transparency(top_alpha)
            glColor4f(*self._faded_color(LENS_COLOR, top_alpha))
            self._draw_cylinder(self.x, self.y, self.balance_z, LENS_RADIUS, LENS_HEIGHT)
            glColor4f(*self._faded_color(RING_LIGHT_COLOR, top_alpha))
            self._draw_ring_cylinder(
                self.x,
                self.y,
                self.balance_z,
                RING_LIGHT_INNER_RADIUS,
                RING_LIGHT_OUTER_RADIUS,
                RING_LIGHT_HEIGHT,
            )
            self._draw_ring_light_glow(
                self.x,
                self.y,
                self.balance_z,
                self._ring_light_levels.get("top", 0),
                -1,
            )
            glColor4f(*self._faded_color(LENS_COLOR, top_alpha))
            self._draw_cylinder(
                self.x,
                self.y,
                self.balance_z + LENS_HEIGHT,
                LENS_TOP_RADIUS,
                LENS_TOP_HEIGHT,
            )
            self._draw_box(
                self.x,
                self.y,
                self.balance_z + LENS_HEIGHT + LENS_TOP_HEIGHT,
                LENS_BLOCK_SIZE,
                LENS_BLOCK_SIZE,
                LENS_BLOCK_HEIGHT,
            )
            glColor4f(*self._faded_color(CAMERA_MARKER_COLOR, top_alpha))
            self._draw_flipped_cylinder(
                self.x,
                self.y,
                self.balance_z - 0.02,
                CAMERA_MARKER_RADIUS,
                CAMERA_MARKER_HEIGHT,
            )
            if show_bottom and self._bottom_camera_origin:
                self._draw_bottom_camera()
            if not self._tool_offsets:
                return
            z_offsets = _nozzle_visual_z_offsets(self._tool_offsets, self.z, self.balance_z)
            z_offsets = _clamp_nozzle_z_offsets(
                self._tool_offsets,
                z_offsets,
                self.x,
                self.y,
                self.balance_z,
                self._feeder_inventory,
                self._feeder_origins,
                self._component_scale,
                self._pcb_model_state,
                self._pcb_model_data,
            )
            poses = _head_connector_local_poses(self._tool_offsets)
            if poses:
                frame_alpha = self._demo_opacity("head_frame")
                self._set_transparency(frame_alpha)
                glColor4f(*self._faded_color(DEEP_SILVER_COLOR, frame_alpha))
                for key, (cx, cy, cz) in zip(("pl", "pr"), poses["connectors"]):
                    self._draw_box(
                        self.x + cx,
                        self.y + cy,
                        self.balance_z + cz + z_offsets.get(key, 0.0),
                        HEAD_CONNECTOR_X,
                        HEAD_CONNECTOR_Y,
                        HEAD_CONNECTOR_Z,
                    )
                glColor4f(*self._faded_color(METAL_SILVER_COLOR, frame_alpha))
                for rx, ry, rz in poses["rails"]:
                    self._draw_box(
                        self.x + rx,
                        self.y + ry,
                        self.balance_z + rz,
                        GUIDE_RAIL_X,
                        GUIDE_RAIL_Y,
                        GUIDE_RAIL_Z,
                    )
                fx, fy, fz, fsx, fsy, fsz = poses["frame"]
                self._draw_box(
                    self.x + fx,
                    self.y + fy,
                    self.balance_z + fz,
                    fsx,
                    fsy,
                    fsz,
                )
                lx, ly, lz, lsx, lsy, lsz = poses["camera_link"]
                self._draw_box(
                    self.x + lx,
                    self.y + ly,
                    self.balance_z + lz,
                    lsx,
                    lsy,
                    lsz,
                )
            for key, (ox, oy) in self._tool_offsets.items():
                nozzle_alpha = self._demo_opacity("nozzle", key)
                self._set_transparency(nozzle_alpha)
                stack_x = self.x + ox
                stack_y = self.y + oy
                stack_z = self.balance_z + NOZZLE_HEIGHT + z_offsets.get(key, 0.0)
                glColor4f(*self._faded_color(NOZZLE_COLOR, nozzle_alpha))
                self._draw_inverted_cone(
                    stack_x,
                    stack_y,
                    stack_z,
                    NOZZLE_RADIUS,
                    NOZZLE_HEIGHT,
                )
                glColor4f(*self._faded_color(METAL_SILVER_COLOR, nozzle_alpha))
                self._draw_cylinder(
                    stack_x,
                    stack_y,
                    stack_z,
                    NOZZLE_BOTTOM1_LINK_RADIUS,
                    NOZZLE_BOTTOM1_LINK_HEIGHT,
                )
                glColor4f(*self._faded_color(BRASS_COLOR, nozzle_alpha))
                self._draw_cylinder(
                    stack_x,
                    stack_y,
                    stack_z + NOZZLE_BOTTOM1_LINK_HEIGHT,
                    NOZZLE_BOTTOM2_LINK_RADIUS,
                    NOZZLE_BOTTOM2_LINK_HEIGHT,
                )
                glColor4f(*self._faded_color(DARK_BLOCK_COLOR, nozzle_alpha))
                self._draw_box(
                    stack_x,
                    stack_y,
                    stack_z + NOZZLE_BOTTOM_LINK_HEIGHT,
                    NOZZLE_BLOCK_SIZE,
                    NOZZLE_BLOCK_SIZE,
                    NOZZLE_BLOCK_HEIGHT,
                )
                glColor4f(*self._faded_color(BRASS_COLOR, nozzle_alpha))
                self._draw_cylinder(
                    stack_x,
                    stack_y,
                    stack_z + NOZZLE_BOTTOM_LINK_HEIGHT + NOZZLE_BLOCK_HEIGHT,
                    NOZZLE_TOP_LINK_RADIUS,
                    NOZZLE_TOP_LINK_HEIGHT,
                )
                glColor4f(*self._faded_color(LIGHT_CAP_COLOR, nozzle_alpha))
                self._draw_cylinder(
                    stack_x,
                    stack_y,
                    stack_z + NOZZLE_BOTTOM_LINK_HEIGHT + NOZZLE_BLOCK_HEIGHT + NOZZLE_TOP_LINK_HEIGHT,
                    NOZZLE_CAP_RADIUS,
                    NOZZLE_CAP_HEIGHT,
                )
            held = _pcb_model_held_component(
                self._pcb_model_data, self._pcb_model_state
            )
            if held:
                nozzle = held["nozzle"]
                tool_x, tool_y = self._tool_offsets.get(nozzle, (0.0, 0.0))
                scale_data = (self._pcb_model_state or {}).get("scale_jp_per_mm") or {}
                scale_x = abs(float(scale_data.get("x", 1.0) or 1.0))
                scale_y = abs(float(scale_data.get("y", 1.0) or 1.0))
                meshes = build_component_meshes(
                    held["package"],
                    scale_x,
                    scale_y,
                    value=held["value"],
                    rotation_degrees=held["rotation_deg"],
                )
                component_height = max(
                    (float(vertices[:, 2].max()) for vertices, _faces, _color in meshes),
                    default=0.0,
                )
                held_base_z = (
                    self.balance_z
                    + z_offsets.get(nozzle, 0.0)
                    - component_height
                    - NOZZLE_CONTACT_CLEARANCE
                )
                self._draw_component_meshes(
                    held["package"],
                    self.x + tool_x - held["contact_x"],
                    self.y + tool_y - held["contact_y"],
                    held_base_z,
                    scale_x,
                    scale_y,
                    value=held["value"],
                    angle=held["rotation_deg"],
                    alpha=self._demo_opacity("nozzle", nozzle),
                )
        def _draw_feeders(self):
            feeder_alpha = self._demo_opacity("feeder")
            self._set_transparency(feeder_alpha)
            for key, origin in sorted(
                self._feeder_origins.items(),
                key=lambda item: _feeder_sort_key(item[0]),
            ):
                if key not in self._active_feeders:
                    continue
                try:
                    x = float(origin[0])
                    y = float(origin[1])
                except (TypeError, ValueError, IndexError):
                    continue
                for color, sx, sy, sz, sw, sd, sh in _feeder_model_boxes(x, y):
                    glColor4f(*self._faded_color(_boost_color(color), feeder_alpha))
                    self._draw_box(sx, sy, sz, sw, sd, sh)
                trap_verts, trap_faces = _feeder_top_trapezoid_mesh(x, y)
                glColor4f(*self._faded_color(
                    _boost_color(FEEDER_BODY_COLOR), feeder_alpha
                ))
                self._draw_triangle_mesh(trap_verts, trap_faces)

        def _draw_feeder_components(self):
            feeder_alpha = self._demo_opacity("feeder_content")
            self._set_transparency(feeder_alpha)
            scale_x = self._component_scale.get("x", 1.0)
            scale_y = self._component_scale.get("y", 1.0)
            tape_base_z = (
                BOARD_TOP_Z - FEEDER_SLOT_DEPTH - FEEDER_SLOT_RECESS + FEEDER_SLOT_FLOOR
            )
            for material in self._feeder_inventory:
                center = material.get("center_jp") or {}
                try:
                    slot = str(material.get("slot", "")).upper()
                    feeder_origin = self._feeder_origins.get(slot)
                    if feeder_origin is None or len(feeder_origin) < 2:
                        continue
                    glColor4f(*self._faded_color(
                        _boost_color(feeder_tape_color(material.get("package"))),
                        feeder_alpha,
                    ))
                    self._draw_box(
                        float(feeder_origin[0]),
                        float(feeder_origin[1]),
                        tape_base_z,
                        FEEDER_SLOT_X - 2.0 * FEEDER_SLOT_WALL,
                        FEEDER_SLOT_Y - 2.0 * FEEDER_SLOT_WALL,
                        FEEDER_TAPE_HEIGHT,
                    )
                    self._draw_component_meshes(
                        material.get("package"),
                        float(center["x"]),
                        float(center["y"]),
                        tape_base_z + FEEDER_TAPE_HEIGHT,
                        scale_x,
                        scale_y,
                        value=material.get("value"),
                        angle=90.0,
                        color_boost=1.75,
                        alpha=feeder_alpha,
                    )
                except (KeyError, TypeError, ValueError):
                    continue

        def _draw_bottom_camera(self):
            x, y, z = self._bottom_camera_origin
            bottom_alpha = self._demo_opacity("bottom_camera")
            self._set_transparency(bottom_alpha)
            glColor4f(*self._faded_color(LENS_COLOR, bottom_alpha))
            self._draw_flipped_cylinder(x, y, z, LENS_RADIUS, LENS_HEIGHT)
            glColor4f(*self._faded_color(RING_LIGHT_COLOR, bottom_alpha))
            self._draw_flipped_ring_cylinder(
                x,
                y,
                z,
                RING_LIGHT_INNER_RADIUS,
                RING_LIGHT_OUTER_RADIUS,
                RING_LIGHT_HEIGHT,
            )
            self._draw_ring_light_glow(
                x,
                y,
                z,
                self._ring_light_levels.get("bottom", 0),
                1,
            )
            glColor4f(*self._faded_color(LENS_COLOR, bottom_alpha))
            self._draw_flipped_cylinder(
                x,
                y,
                z - LENS_HEIGHT,
                LENS_TOP_RADIUS,
                LENS_TOP_HEIGHT,
            )
            self._draw_flipped_box(
                x,
                y,
                z - LENS_HEIGHT - LENS_TOP_HEIGHT,
                LENS_BLOCK_SIZE,
                LENS_BLOCK_SIZE,
                LENS_BLOCK_HEIGHT,
            )
            glColor4f(*self._faded_color(CAMERA_MARKER_COLOR, bottom_alpha))
            self._draw_cylinder(
                x,
                y,
                z + 0.02,
                CAMERA_MARKER_RADIUS,
                CAMERA_MARKER_HEIGHT,
            )

        def _draw_board(self):
            """Draw the PCB board as a dark cuboid with a 9x9 top grid."""
            board_alpha = self._demo_opacity("workdesk")
            self._set_transparency(board_alpha)
            v = [(px + self.h, py, pz) for px, py, pz in self._board_verts]
            # 6 faces as quads
            quads = [
                (0,1,2,3),  # bottom
                (4,5,6,7),  # top
                (0,1,5,4),  # front (BR-TR edge)
                (1,2,6,5),  # right (TR-TL edge)
                (2,3,7,6),  # back (TL-BL edge)
                (3,0,4,7),  # left (BL-BR edge)
            ]
            glColor4f(*self._faded_color(BOARD_DARK_COLOR, board_alpha))
            for i0, i1, i2, i3 in quads:
                glBegin(GL_QUADS)
                glVertex3f(*v[i0]); glVertex3f(*v[i1])
                glVertex3f(*v[i2]); glVertex3f(*v[i3])
                glEnd()
            # Wireframe edges
            glColor4f(*self._faded_color((0.25, 0.25, 0.25, 1.0), board_alpha))
            edges = [(0,1),(1,2),(2,3),(3,0),  # bottom
                     (4,5),(5,6),(6,7),(7,4),  # top
                     (0,4),(1,5),(2,6),(3,7)]  # vertical
            glBegin(GL_LINES)
            for a, b in edges:
                glVertex3f(*v[a]); glVertex3f(*v[b])
            glEnd()
            glLineWidth(float(BOARD_GRID_WIDTH))
            glColor4f(*self._faded_color(BOARD_GRID_COLOR, board_alpha))
            glBegin(GL_LINES)
            for a, b in _grid_lines_for_quad(v[4:8], divisions=9):
                glVertex3f(*a); glVertex3f(*b)
            glEnd()
            glLineWidth(1.0)

        def _draw_pcb_model(self):
            state = self._pcb_model_state
            model = self._pcb_model_data
            if not state or not model:
                return
            board_alpha = self._demo_opacity("workdesk")
            self._set_transparency(board_alpha)
            glPushMatrix()
            try:
                glTranslatef(float(self.h), 0.0, 0.0)
                pcb = model.get("pcb") or {}
                size = pcb.get("size_mm") or {}
                scale_data = state.get("scale_jp_per_mm") or {}
                scale_x = abs(float(scale_data.get("x", 1.0) or 1.0))
                scale_y = abs(float(scale_data.get("y", 1.0) or 1.0))
                width_y = float(size.get("width", 0.0) or 0.0) * scale_y
                depth_x = float(size.get("height", 0.0) or 0.0) * scale_x
                thickness = max(0.05, float(state.get("thickness", 0.5) or 0.5))
                pose = state.get("center_jp") or {}
                ox = float(pose.get("x", 0.0) or 0.0)
                oy = float(pose.get("y", 0.0) or 0.0)
                board_rotation = float(state.get("rotation_deg", 180.0) or 0.0)
                board_pose_rotation = float(
                    state.get("pose_rotation_deg", board_rotation - 180.0) or 0.0
                )
                if width_y <= 0 or depth_x <= 0:
                    return
                glColor4f(*self._faded_color(PCB_MODEL_BODY_COLOR, board_alpha))
                glPushMatrix()
                try:
                    glTranslatef(ox, oy, 0.0)
                    glRotatef(board_pose_rotation, 0.0, 0.0, 1.0)
                    self._draw_box(
                        0.0,
                        0.0,
                        BOARD_TOP_Z,
                        depth_x,
                        width_y,
                        thickness,
                    )
                finally:
                    glPopMatrix()

                glLineWidth(1.0)
                for _designator, points, color in _pcb_model_component_status_lines(
                    model, state
                ):
                    glColor4f(*self._faded_color(color, board_alpha))
                    glBegin(GL_LINES)
                    glVertex3f(*points[0])
                    glVertex3f(*points[1])
                    glEnd()
                completed = {
                    str(value).strip().upper()
                    for value in (state.get("completed_designators") or [])
                }
                released_components = state.get("released_components") or {}
                board_components = completed | {
                    str(value).strip().upper() for value in released_components
                }
                visible = {
                    str(value).strip().upper()
                    for value in (state.get("visible_designators") or [])
                }
                materials = state.get("component_materials") or {}
                center = pcb.get("center") or [0.0, 0.0]
                for component in model.get("components") or []:
                    designator = str(component.get("designator", "") or "").strip().upper()
                    if designator not in board_components or (visible and designator not in visible):
                        continue
                    material = materials.get(designator) or {}
                    package = material.get("package") or component.get("package")
                    local_x, local_y = _pcb_model_local_xy(
                        component.get("x", 0.0),
                        component.get("y", 0.0),
                        center,
                        (scale_x, scale_y),
                        board_rotation,
                    )
                    nominal_x = ox + local_x
                    nominal_y = oy + local_y
                    nominal_angle = pcb_component_rotation(
                        component.get("rotation", 0.0), board_rotation
                    )
                    inspection = (state.get("placement_inspections") or {}).get(
                        designator
                    ) or {}
                    released = _pcb_model_released_component(state, designator)
                    base_x = released["x"] if released else nominal_x
                    base_y = released["y"] if released else nominal_y
                    base_angle = nominal_angle
                    if released:
                        base_angle = pcb_component_rotation(
                            released["rotation_deg"], board_rotation
                        ) + float(
                            released["pick_inspection"].get(
                                "rotation_offset_deg", 0.0
                            )
                            or 0.0
                        )
                    if released:
                        glEnable(GL_BLEND)
                        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
                        glDepthMask(GL_FALSE)
                    self._draw_component_meshes(
                        package,
                        base_x,
                        base_y,
                        BOARD_TOP_Z + thickness + 0.04,
                        scale_x,
                        scale_y,
                        value=material.get("value") or component.get("value"),
                        angle=base_angle,
                        alpha=(
                            0.0
                            if inspection.get("found", False)
                            else (RELEASED_COMPONENT_ALPHA if released else 1.0)
                        ) * board_alpha,
                    )
                    if released:
                        glDepthMask(GL_TRUE)
                        glDisable(GL_BLEND)
                    if not inspection.get("found", False):
                        continue
                    inspect_x, inspect_y, inspect_angle = _pcb_model_inspection_adjustment(
                        state, designator
                    )
                    self._draw_component_meshes(
                        package,
                        nominal_x + inspect_x,
                        nominal_y + inspect_y,
                        BOARD_TOP_Z + thickness + 0.12,
                        scale_x,
                        scale_y,
                        value=material.get("value") or component.get("value"),
                        angle=nominal_angle + inspect_angle,
                        alpha=board_alpha,
                    )
                self.qglColor(QColor.fromRgbF(*PCB_MODEL_INSPECTION_TEXT_COLOR))
                for label_index, (label_pos, label_text) in enumerate(
                    _pcb_model_inspection_labels(model, state)
                ):
                    point_size = _inspection_label_lod(
                        self.cam_distance, label_index
                    )
                    if point_size is None:
                        continue
                    self.renderText(
                        float(label_pos[0]),
                        float(label_pos[1]),
                        float(label_pos[2]),
                        label_text,
                        QFont("Arial", point_size),
                    )
                # Restore the yellow post-placement guide and purple pickup
                # measurement labels.  These are visual evidence only and do
                # not alter the nominal component mesh when target matching
                # was unavailable.
                self.qglColor(QColor.fromRgbF(*PCB_MODEL_PICK_INSPECTION_TEXT_COLOR))
                glLineWidth(2.0)
                for _designator, line_points, label_pos, label_text in (
                    _pcb_model_pick_inspection_lines(model, state)
                ):
                    glColor4f(*PCB_MODEL_PICK_INSPECTION_LINE_COLOR)
                    glBegin(GL_LINES)
                    glVertex3f(*line_points[0])
                    glVertex3f(*line_points[1])
                    glEnd()
                    self.qglColor(
                        QColor.fromRgbF(*PCB_MODEL_PICK_INSPECTION_TEXT_COLOR)
                    )
                    self.renderText(
                        float(label_pos[0]),
                        float(label_pos[1]),
                        float(label_pos[2]),
                        label_text,
                        QFont("Arial", 9),
                    )
                glLineWidth(1.0)
            except Exception:
                return
            finally:
                glPopMatrix()
