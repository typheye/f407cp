"""PyQtGraph OpenGL implementation for the JanPNP 3D preview."""
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
    class DemoGLViewWidget(GLViewWidget):
        """GL view that can temporarily reject all manual camera input."""

        def __init__(self, parent=None):
            super().__init__(parent)
            self._demo_input_locked = False

        def set_demo_input_locked(self, locked):
            self._demo_input_locked = bool(locked)
            if self._demo_input_locked:
                self.keysPressed.clear()
                self.keyTimer.stop()

        def _reject_demo_input(self, event):
            if not self._demo_input_locked:
                return False
            event.accept()
            return True

        def mousePressEvent(self, event):
            if not self._reject_demo_input(event):
                super().mousePressEvent(event)

        def mouseReleaseEvent(self, event):
            if not self._reject_demo_input(event):
                super().mouseReleaseEvent(event)

        def mouseMoveEvent(self, event):
            if not self._reject_demo_input(event):
                super().mouseMoveEvent(event)

        def mouseDoubleClickEvent(self, event):
            if not self._reject_demo_input(event):
                super().mouseDoubleClickEvent(event)

        def wheelEvent(self, event):
            if not self._reject_demo_input(event):
                super().wheelEvent(event)

        def keyPressEvent(self, event):
            if not self._reject_demo_input(event):
                super().keyPressEvent(event)

        def keyReleaseEvent(self, event):
            if not self._reject_demo_input(event):
                super().keyReleaseEvent(event)

    class GLW3D(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            layout = QVBoxLayout(self); layout.setContentsMargins(0,0,0,0)
            self.v = DemoGLViewWidget(); self.v.setCameraPosition(distance=400)
            layout.addWidget(self.v)
            # Hide the base environment grid; the PCB top grid is enough context.
            self.base_grid = GLGridItem(); self.base_grid.scale(20,20,20)
            self.base_grid.setVisible(False)
            # Red X-axis (forward), Green Y-axis (right)
            self.x_axis = GLLinePlotItem(pos=np.array([[0,0,0],[280,0,0]]), color=(1,0,0,1), width=3, antialias=True)
            self.v.addItem(self.x_axis)
            self.y_axis = GLLinePlotItem(pos=np.array([[0,0,0],[0,280,0]]), color=(0,1,0,1), width=3, antialias=True)
            self.v.addItem(self.y_axis)
            # Origin marker
            self.origin = GLScatterPlotItem(pos=np.array([[0,0,0]]), size=10, color=(1,1,1,0.8))
            self.v.addItem(self.origin)
            self._model_pose = np.array([0.0, 0.0, DEFAULT_BALANCE_Z], dtype=float)
            self._tool_offsets = {"pl": (0.0, 0.0), "pr": (0.0, 0.0)}
            self._tool_offset_applied = {"pl": (0.0, 0.0), "pr": (0.0, 0.0)}
            self._nozzle_z_applied = {"pl": 0.0, "pr": 0.0}
            self._ring_light_levels = {"top": 0, "bottom": 0}
            self._display_visibility = {
                "pick_top_camera": True,
                "bottom_camera": True,
                "feeders": True,
                "workdesk": True,
            }
            self._demo_mode = False
            self._demo_saved_camera = None
            self._demo_saved_visibility = None
            self._demo_emphasis = ("overview", None)
            self._add_machine_model()
            self._bottom_camera_origin = None
            self._workdesk_items = []
            self._board_geometry_items = []
            self._workdesk_bounds_signature = None
            self._h_position = 0.0
            self._add_board()
            self._feeder_items = {}
            self._feeder_item_pos = {}
            self._feeder_component_items = []
            self._feeder_component_signature = None
            self._feeder_inventory = []
            self._component_scale = {"x": 1.0, "y": 1.0}
            self.set_feeders(DEFAULT_FEEDERS_ORIGIN, DEFAULT_FEEDERS_ORIGIN.keys())
            self._pcb_model_revision = None
            self._pcb_model_signature = None
            self._pcb_model_items = []
            self._pcb_model_label_items = []
            self._held_component_items = []
            self._held_component_nozzle = None
            self._pcb_model_state = None
            self._pcb_model_data = None
            self.trail = GLLinePlotItem(pos=np.zeros((1,3)), color=(1,0.5,0,1.0), width=2, antialias=True)
            self.trail.setGLOptions("additive")
            self.trail.setVisible(False)  # off by default
            self.v.addItem(self.trail)
            self._board_scan_signature = None
            self._board_scan_mosaic_item = None
            self._board_scan_item = GLLinePlotItem(
                pos=np.zeros((1, 3)),
                color=(1.0, 1.0, 1.0, 0.95),
                width=2,
                antialias=True,
                mode="line_strip",
            )
            self._board_scan_item.setGLOptions("translucent")
            self._board_scan_item.setVisible(False)
            self.v.addItem(self._board_scan_item)
            self._workdesk_items.append(self._board_scan_item)

        def set_background_color(self, color):
            """Match the OpenGL viewport to the active Qt window palette."""
            self.v.setBackgroundColor(QColor(color))
            self.v.update()

        def set_demo_mode(self, enabled):
            enabled = bool(enabled)
            if enabled == self._demo_mode:
                return
            if enabled:
                center = self.v.opts.get("center")
                self._demo_saved_camera = {
                    "center": (
                        float(center.x()), float(center.y()), float(center.z())
                    ),
                    "distance": float(self.v.opts.get("distance", 400.0)),
                    "elevation": float(self.v.opts.get("elevation", 30.0)),
                    "azimuth": float(self.v.opts.get("azimuth", 45.0)),
                }
                self._demo_saved_visibility = dict(self._display_visibility)
            self._demo_mode = enabled
            self.v.set_demo_input_locked(enabled)
            if not enabled:
                self._demo_emphasis = ("overview", None)
                self._apply_demo_scene_emphasis()
                for part, visible in (self._demo_saved_visibility or {}).items():
                    self.set_scene_part_visible(part, visible)
                camera = self._demo_saved_camera
                if camera:
                    self.set_demo_camera(**camera)
                self._demo_saved_camera = None
                self._demo_saved_visibility = None

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
            feeder_opacity = max(
                0.0, min(1.0, float((opacity or {}).get("feeders", 1.0)))
            )
            content_opacity = max(
                0.0,
                min(1.0, float((opacity or {}).get("feeder_contents", 1.0))),
            )
            items = [
                item
                for feeder_items in getattr(self, "_feeder_items", {}).values()
                for item in feeder_items
            ]
            for item in items:
                self._set_item_demo_opacity(item, feeder_opacity)
            for item in getattr(self, "_feeder_component_items", []):
                self._set_item_demo_opacity(item, content_opacity)

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
                if group == "head_frame" or group == "top_camera":
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

        def _set_item_demo_opacity(self, item, opacity):
            if item is None:
                return
            opacity = max(0.0, min(1.0, float(opacity)))
            if getattr(item, "_demo_scene_opacity", None) == opacity:
                return
            if GLImageItem is not None and isinstance(item, GLImageItem):
                if not hasattr(item, "_demo_base_image"):
                    item._demo_base_image = np.asarray(item.data).copy()
                pixels = item._demo_base_image.copy()
                if pixels.ndim >= 3 and pixels.shape[-1] >= 4:
                    pixels[..., 3] = np.asarray(
                        pixels[..., 3], dtype=float
                    ) * opacity
                    item.setData(pixels.astype(item._demo_base_image.dtype))
                item._demo_scene_opacity = opacity
                return

            if not hasattr(item, "_demo_base_color"):
                color = None
                if isinstance(item, GLMeshItem):
                    color = item.opts.get("color")
                elif hasattr(item, "color"):
                    color = item.color
                if isinstance(color, QColor):
                    color = color.getRgbF()
                if color is not None:
                    item._demo_base_color = np.asarray(color, dtype=float).copy()
                item._demo_base_gl_options = dict(
                    getattr(item, "_GLGraphicsItem__glOpts", {})
                )

            base = getattr(item, "_demo_base_color", None)
            if base is not None:
                color = np.asarray(base, dtype=float).copy()
                if color.ndim == 1 and color.size >= 4:
                    color[3] = base[3] * opacity
                elif color.ndim >= 2 and color.shape[-1] >= 4:
                    color[..., 3] = base[..., 3] * opacity
                if isinstance(item, GLMeshItem):
                    item._demo_translucent = opacity < 0.999
                    item.setColor(tuple(color) if color.ndim == 1 else color)
                elif isinstance(item, GLTextItem) and color.ndim == 1:
                    item.setData(color=QColor.fromRgbF(*color[:4]))
                elif isinstance(item, GLLinePlotItem):
                    item.setData(color=tuple(color) if color.ndim == 1 else color)
            if hasattr(item, "setGLOptions"):
                if opacity < 0.999:
                    item.setGLOptions("translucent")
                else:
                    original = getattr(item, "_demo_base_gl_options", None)
                    if original:
                        item.setGLOptions(original)
            item._demo_scene_opacity = opacity

        def _apply_demo_scene_emphasis(self):
            subject, active_nozzle = self._demo_emphasis
            top_camera_items = [
                getattr(self, "_camera_marker_item", None),
                getattr(self, "_lens_item", None),
                getattr(self, "_ring_light_item", None),
            ]
            top_camera_items.extend(getattr(self, "_lens_stack_items", []))
            groups = [
                ("top_camera", None, top_camera_items),
                ("bottom_camera", None, getattr(self, "_bottom_camera_items", [])),
                (
                    "head_frame",
                    None,
                    list(getattr(self, "_head_connector_items", []))
                    + list(getattr(self, "_head_extra_items", [])),
                ),
                (
                    "feeder",
                    None,
                    [item for items in getattr(self, "_feeder_items", {}).values() for item in items]
                    + list(getattr(self, "_feeder_component_items", [])),
                ),
            ]
            held_ids = {id(item) for item in getattr(self, "_held_component_items", [])}
            work_items = list(getattr(self, "_workdesk_items", [])) + [
                item
                for item in getattr(self, "_pcb_model_items", [])
                if id(item) not in held_ids
            ]
            groups.append(("workdesk", None, work_items))
            for nozzle, item in getattr(self, "_nozzle_items", {}).items():
                nozzle_items = [item] + list(
                    getattr(self, "_nozzle_stack_items", {}).get(nozzle, [])
                )
                if nozzle == getattr(self, "_held_component_nozzle", None):
                    nozzle_items.extend(getattr(self, "_held_component_items", []))
                groups.append(("nozzle", nozzle, nozzle_items))

            seen = set()
            for group, nozzle, items in groups:
                opacity = self._demo_group_opacity(
                    subject, group, nozzle, active_nozzle
                )
                for item in items:
                    if item is None or id(item) in seen:
                        continue
                    seen.add(id(item))
                    self._set_item_demo_opacity(item, opacity)
            self._update_ring_light_glow_items()

        def set_demo_scene_emphasis(self, subject, active_nozzle=None):
            if not self._demo_mode:
                return
            active_nozzle = str(active_nozzle or "").lower() or None
            self._demo_emphasis = (str(subject or "overview"), active_nozzle)
            self._apply_demo_scene_emphasis()

        def set_demo_camera(self, center, distance, elevation, azimuth):
            self.v.setCameraPosition(
                pos=QVector3D(*[float(value) for value in center]),
                distance=float(distance),
                elevation=float(elevation),
                azimuth=float(azimuth),
            )

        def _apply_mesh_color(self, item, color):
            try:
                item.setColor(color)
            except Exception:
                try:
                    item.opts["color"] = color
                    item.update()
                except Exception:
                    pass

        def set_trail_visible(self, v):
            self.trail.setVisible(v)

        def clear_trail(self):
            self.trail.setData(pos=np.zeros((1, 3), dtype=float))

        def _top_machine_items(self):
            items = [
                getattr(self, "_camera_marker_item", None),
                getattr(self, "_lens_item", None),
                getattr(self, "_ring_light_item", None),
            ]
            items.extend(getattr(self, "_top_ring_glow_items", []))
            items.extend(getattr(self, "_lens_stack_items", []))
            items.extend(getattr(self, "_head_connector_items", []))
            items.extend(getattr(self, "_head_extra_items", []))
            items.extend(getattr(self, "_nozzle_items", {}).values())
            for stack in getattr(self, "_nozzle_stack_items", {}).values():
                items.extend(stack)
            items.extend(getattr(self, "_held_component_items", []))
            return [item for item in items if item is not None]

        def set_scene_part_visible(self, part, visible):
            if part not in self._display_visibility:
                return
            visible = bool(visible)
            self._display_visibility[part] = visible
            if part == "pick_top_camera":
                for item in self._top_machine_items():
                    item.setVisible(visible)
                self._update_ring_light_glow_items()
            elif part == "bottom_camera":
                available = self._bottom_camera_origin is not None
                for item in self._bottom_camera_items:
                    item.setVisible(visible and available)
                self._update_ring_light_glow_items()
            elif part == "feeders":
                for key, items in self._feeder_items.items():
                    item_visible = visible and key in self._active_feeders
                    for item in items:
                        item.setVisible(item_visible)
                for item in self._feeder_component_items:
                    item.setVisible(visible)
            elif part == "workdesk":
                for item in self._workdesk_items:
                    item.setVisible(visible)
                scan_active = bool(
                    self._board_scan_signature and self._board_scan_signature[1]
                )
                self._board_scan_item.setVisible(False)
                if self._board_scan_mosaic_item is not None:
                    self._board_scan_mosaic_item.setVisible(visible and scan_active)

        def set_board_scan(self, state):
            state = state or {}
            outline = state.get("outline_jp") or []
            mosaic_png = state.get("mosaic_png")
            bounds = state.get("mosaic_bounds_jp") or {}
            try:
                bounds_signature = tuple(
                    round(float(bounds[key]), 4)
                    for key in ("x_min", "x_max", "y_min", "y_max")
                )
                if bounds_signature != self._workdesk_bounds_signature:
                    self._add_board(bounds)
                    self._workdesk_bounds_signature = bounds_signature
            except (KeyError, TypeError, ValueError):
                pass
            active = bool(state.get("active")) and (
                len(outline) >= 2 or bool(mosaic_png)
            )
            signature = (
                int(state.get("revision", 0) or 0),
                active,
                bool(self._display_visibility.get("workdesk", True)),
            )
            if signature == self._board_scan_signature:
                return
            self._board_scan_signature = signature
            if self._board_scan_mosaic_item is not None:
                try:
                    self.v.removeItem(self._board_scan_mosaic_item)
                except Exception:
                    pass
                try:
                    self._workdesk_items.remove(self._board_scan_mosaic_item)
                except ValueError:
                    pass
                self._board_scan_mosaic_item = None
            if not active:
                self._board_scan_item.setData(pos=np.zeros((1, 3), dtype=float))
                self._board_scan_item.setVisible(False)
                return
            if mosaic_png and GLImageItem is not None:
                try:
                    raw = base64.b64decode(mosaic_png, validate=True)
                    image = QImage()
                    if image.loadFromData(raw):
                        image = image.convertToFormat(QImage.Format_RGBA8888)
                        width = image.width()
                        height = image.height()
                        ptr = image.bits()
                        ptr.setsize(image.byteCount())
                        pixels = np.frombuffer(ptr, np.uint8).reshape(
                            (height, width, 4)
                        ).copy()
                        pixels = np.transpose(pixels, (1, 0, 2)).copy()
                        x_min = float(bounds["x_min"])
                        x_max = float(bounds["x_max"])
                        y_min = float(bounds["y_min"])
                        y_max = float(bounds["y_max"])
                        texture = GLImageItem(
                            pixels, smooth=True, glOptions="translucent"
                        )
                        texture.scale(
                            (x_max - x_min) / max(1, pixels.shape[0]),
                            (y_max - y_min) / max(1, pixels.shape[1]),
                            1.0,
                        )
                        texture.translate(
                            x_min + self._h_position,
                            y_min,
                            BOARD_TOP_Z + 0.45,
                        )
                        self.v.addItem(texture)
                        texture.setVisible(
                            bool(self._display_visibility.get("workdesk", True))
                        )
                        self._board_scan_mosaic_item = texture
                        self._workdesk_items.append(texture)
                except (KeyError, TypeError, ValueError) as exc:
                    print(f"[Tel] Board scan mosaic render failed: {exc}")
            points = []
            for point in outline:
                try:
                    points.append(
                        (
                            float(point["x"]) + self._h_position,
                            float(point["y"]),
                            BOARD_TOP_Z + 1.0,
                        )
                    )
                except (KeyError, TypeError, ValueError):
                    continue
            if len(points) >= 2:
                points.append(points[0])
                self._board_scan_item.setData(pos=np.asarray(points, dtype=float))
                self._board_scan_item.setVisible(False)
            else:
                self._board_scan_item.setData(pos=np.zeros((1, 3), dtype=float))
                self._board_scan_item.setVisible(False)

        def set_h_position(self, h):
            """Move the workdesk and board-owned PCB content along scene +X."""
            target = float(h or 0.0)
            delta = target - self._h_position
            if delta:
                for item in self._workdesk_items:
                    item.translate(float(delta), 0.0, 0.0)
                held_ids = {id(item) for item in self._held_component_items}
                for item in self._pcb_model_items:
                    if id(item) not in held_ids:
                        item.translate(float(delta), 0.0, 0.0)
            self._h_position = target

        def set_pose(self, x, y, z, trail, balance_z=DEFAULT_BALANCE_Z, h=0.0):
            self.set_h_position(h)
            self._move_machine_model(float(x or 0.0), float(y or 0.0), float(z or 0.0), balance_z)
            if len(trail) >= 2:
                self.trail.setData(pos=np.array(trail))
            else:
                self.clear_trail()

        def set_tool_offsets(self, offsets):
            if not offsets:
                return
            for key in ("pl", "pr"):
                if key not in offsets:
                    continue
                new_offset = (float(offsets[key][0]), float(offsets[key][1]))
                old_offset = self._tool_offset_applied.get(key, (0.0, 0.0))
                dx = new_offset[0] - old_offset[0]
                dy = new_offset[1] - old_offset[1]
                item = self._nozzle_items.get(key)
                if item and (dx or dy):
                    item.translate(dx, dy, 0.0)
                for part in self._nozzle_stack_items.get(key, []):
                    if dx or dy:
                        part.translate(dx, dy, 0.0)
                if key == self._held_component_nozzle:
                    for held_item in self._held_component_items:
                        held_item.translate(dx, dy, 0.0)
                if item:
                    item.setVisible(self._display_visibility["pick_top_camera"])
                for part in self._nozzle_stack_items.get(key, []):
                    part.setVisible(self._display_visibility["pick_top_camera"])
                self._tool_offsets[key] = new_offset
                self._tool_offset_applied[key] = new_offset
            self._update_head_connector_items()

        def set_bottom_camera_origin(self, origin):
            if not origin:
                return
            new_origin = np.array([float(origin[0]), float(origin[1]), 0.0], dtype=float)
            if self._bottom_camera_origin is None:
                delta = new_origin
                for item in self._bottom_camera_items:
                    item.setVisible(self._display_visibility["bottom_camera"])
                for item in self._bottom_ring_glow_items:
                    item.setVisible(
                        self._display_visibility["bottom_camera"]
                        and self._ring_light_levels.get("bottom", 0) > 0
                    )
            else:
                delta = new_origin - self._bottom_camera_origin
            if np.any(delta):
                for item in self._bottom_camera_items:
                    item.translate(float(delta[0]), float(delta[1]), float(delta[2]))
                for item in self._bottom_ring_glow_items:
                    item.translate(float(delta[0]), float(delta[1]), float(delta[2]))
            self._bottom_camera_origin = new_origin

        def set_ring_light_levels(self, top_level=0, bottom_level=0):
            new_levels = {
                "top": max(0, min(100, int(top_level or 0))),
                "bottom": max(0, min(100, int(bottom_level or 0))),
            }
            if new_levels == self._ring_light_levels:
                return
            self._ring_light_levels = new_levels
            self._update_ring_light_glow_items()

        def set_feeders(self, origins, active_keys):
            if not origins:
                return
            active_keys = set(active_keys or [])
            self._active_feeders = active_keys
            for key, origin in sorted(origins.items(), key=lambda item: _feeder_sort_key(item[0])):
                try:
                    x = float(origin[0])
                    y = float(origin[1])
                except (TypeError, ValueError, IndexError):
                    continue
                if key not in self._feeder_items:
                    items = []
                    for color, sx, sy, sz, sw, sd, sh in _feeder_model_boxes(x, y):
                        verts, faces = _mesh_box(sw, sd, sh)
                        item = SolidGLMeshItem(
                            meshdata=pg.opengl.MeshData(vertexes=verts, faces=faces),
                            color=color,
                            smooth=False,
                            shader=FEEDER_SHADER,
                            glOptions="opaque",
                        )
                        item.translate(sx, sy, sz)
                        self.v.addItem(item)
                        items.append(item)
                    verts, faces = _feeder_top_trapezoid_mesh(x, y)
                    top_item = SolidGLMeshItem(
                        meshdata=pg.opengl.MeshData(vertexes=verts, faces=faces),
                        color=FEEDER_BODY_COLOR,
                        smooth=False,
                        shader=FEEDER_SHADER,
                        glOptions="opaque",
                    )
                    self.v.addItem(top_item)
                    items.append(top_item)
                    self._feeder_items[key] = tuple(items)
                    self._feeder_item_pos[key] = np.array([x, y, 0.0], dtype=float)
                else:
                    old = self._feeder_item_pos.get(key, np.array([x, y, 0.0], dtype=float))
                    new = np.array([x, y, 0.0], dtype=float)
                    delta = new - old
                    if np.any(delta):
                        for item in self._feeder_items[key]:
                            item.translate(float(delta[0]), float(delta[1]), 0.0)
                    self._feeder_item_pos[key] = new
                visible = self._display_visibility["feeders"] and key in active_keys
                for item in self._feeder_items[key]:
                    item.setVisible(visible)

        def set_feeder_components(self, inventory, scale=None):
            scale = scale or {}
            sx = abs(float(scale.get("x", 1.0) or 1.0))
            sy = abs(float(scale.get("y", 1.0) or 1.0))
            self._feeder_inventory = [dict(item) for item in (inventory or [])]
            self._component_scale = {"x": sx, "y": sy}
            signature = (
                round(sx, 6),
                round(sy, 6),
                tuple(
                    sorted(
                        (
                            str(item.get("slot", "")),
                            str(item.get("package", "")),
                            str(item.get("value", "")),
                            round(float((item.get("center_jp") or {}).get("x", 0.0)), 4),
                            round(float((item.get("center_jp") or {}).get("y", 0.0)), 4),
                        )
                        for item in (inventory or [])
                    )
                ),
            )
            if signature == self._feeder_component_signature:
                return
            for item in self._feeder_component_items:
                try:
                    self.v.removeItem(item)
                except Exception:
                    pass
            self._feeder_component_items = []
            tape_base_z = (
                BOARD_TOP_Z - FEEDER_SLOT_DEPTH - FEEDER_SLOT_RECESS + FEEDER_SLOT_FLOOR
            )
            for material in inventory or []:
                center = material.get("center_jp") or {}
                try:
                    x = float(center["x"])
                    y = float(center["y"])
                except (KeyError, TypeError, ValueError):
                    continue
                slot = str(material.get("slot", "")).upper()
                feeder_pos = self._feeder_item_pos.get(slot)
                if feeder_pos is None:
                    continue
                tape_vertices, tape_faces = _mesh_box(
                    FEEDER_SLOT_X - 2.0 * FEEDER_SLOT_WALL,
                    FEEDER_SLOT_Y - 2.0 * FEEDER_SLOT_WALL,
                    FEEDER_TAPE_HEIGHT,
                )
                tape = SolidGLMeshItem(
                    meshdata=pg.opengl.MeshData(
                        vertexes=tape_vertices, faces=tape_faces
                    ),
                    color=feeder_tape_color(material.get("package")),
                    smooth=False,
                    shader=FEEDER_SHADER,
                    glOptions="opaque",
                )
                tape.translate(
                    float(feeder_pos[0]), float(feeder_pos[1]), tape_base_z
                )
                self.v.addItem(tape)
                tape.setVisible(self._display_visibility["feeders"])
                self._feeder_component_items.append(tape)
                for vertices, faces, color in build_component_meshes(
                    material.get("package"),
                    sx,
                    sy,
                    value=material.get("value"),
                    rotation_degrees=90.0,
                ):
                    mesh = SolidGLMeshItem(
                        meshdata=pg.opengl.MeshData(vertexes=vertices, faces=faces),
                        color=color,
                        smooth=False,
                        shader=FEEDER_SHADER,
                        glOptions="opaque",
                    )
                    mesh.translate(x, y, tape_base_z + FEEDER_TAPE_HEIGHT)
                    self.v.addItem(mesh)
                    mesh.setVisible(self._display_visibility["feeders"])
                    self._feeder_component_items.append(mesh)
            self._feeder_component_signature = signature

        def clear_pcb_model(self):
            for item in self._pcb_model_items:
                try:
                    self.v.removeItem(item)
                except Exception:
                    try:
                        item.setVisible(False)
                    except Exception:
                        pass
            self._pcb_model_items = []
            self._pcb_model_label_items = []
            self._held_component_items = []
            self._held_component_nozzle = None
            self._pcb_model_revision = None
            self._pcb_model_signature = None

        def _update_pcb_label_lod(self):
            distance = float(self.v.opts.get("distance", 400.0) or 400.0)
            for index, label in enumerate(self._pcb_model_label_items):
                point_size = _inspection_label_lod(distance, index)
                label.setVisible(point_size is not None)
                if point_size is not None:
                    label.setData(font=QFont("Arial", point_size))

        def set_pcb_model(self, state, model, preview=None):
            if not state or not state.get("active") or not model:
                self._pcb_model_state = None
                self._pcb_model_data = None
                if self._pcb_model_items:
                    self.clear_pcb_model()
                return
            self._pcb_model_state = dict(state)
            self._pcb_model_data = dict(model)
            revision = state.get("revision")
            signature = (
                revision,
                float(state.get("rotation_deg", 180.0) or 0.0),
                float(state.get("pose_rotation_deg", 0.0) or 0.0),
                tuple(state.get("completed_designators") or []),
                tuple(state.get("failed_designators") or []),
                json.dumps(
                    state.get("placement_inspections") or {},
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                json.dumps(
                    state.get("pick_inspections") or {},
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                json.dumps(
                    state.get("held_component") or {},
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                json.dumps(
                    state.get("released_components") or {},
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            )
            if signature == self._pcb_model_signature:
                self._update_pcb_label_lod()
                return
            self.clear_pcb_model()
            try:
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

                verts, faces = _mesh_box(depth_x, width_y, thickness)
                body = SolidGLMeshItem(
                    meshdata=pg.opengl.MeshData(vertexes=verts, faces=faces),
                    color=PCB_MODEL_BODY_COLOR,
                    smooth=False,
                    shader="shaded",
                    glOptions="opaque",
                )
                body_transform = QMatrix4x4()
                body_transform.translate(ox, oy, BOARD_TOP_Z)
                body_transform.rotate(board_pose_rotation, 0.0, 0.0, 1.0)
                body.setTransform(body_transform)
                self.v.addItem(body)
                self._pcb_model_items.append(body)

                has_texture = preview is not None and GLImageItem is not None
                if has_texture:
                    texture = GLImageItem(preview, smooth=True, glOptions="opaque")
                    img_x = max(1, int(preview.shape[0]))
                    img_y = max(1, int(preview.shape[1]))
                    texture_transform = QMatrix4x4()
                    texture_transform.translate(
                        ox, oy, BOARD_TOP_Z + thickness + 0.03
                    )
                    texture_transform.rotate(
                        board_pose_rotation, 0.0, 0.0, 1.0
                    )
                    texture_transform.translate(-depth_x / 2.0, -width_y / 2.0, 0.0)
                    texture_transform.scale(
                        depth_x / img_x, width_y / img_y, 1.0
                    )
                    texture.setTransform(texture_transform)
                    self.v.addItem(texture)
                    self._pcb_model_items.append(texture)
                for _designator, pos, color in _pcb_model_component_status_lines(
                    model, state
                ):
                    line = GLLinePlotItem(
                        pos=pos,
                        color=color,
                        width=1,
                        antialias=True,
                    )
                    line.setGLOptions("opaque")
                    self.v.addItem(line)
                    self._pcb_model_items.append(line)
                for label_pos, label_text in _pcb_model_inspection_labels(model, state):
                    label = GLTextItem(
                        pos=label_pos,
                        color=QColor.fromRgbF(*PCB_MODEL_INSPECTION_TEXT_COLOR),
                        text=label_text,
                        font=QFont("Arial", 8),
                    )
                    label.setGLOptions("translucent")
                    self.v.addItem(label)
                    self._pcb_model_items.append(label)
                    self._pcb_model_label_items.append(label)
                for _designator, line_points, label_pos, label_text in (
                    _pcb_model_pick_inspection_lines(model, state)
                ):
                    line = GLLinePlotItem(
                        pos=np.asarray(line_points, dtype=float),
                        color=PCB_MODEL_PICK_INSPECTION_LINE_COLOR,
                        width=2,
                        antialias=True,
                    )
                    line.setGLOptions("translucent")
                    self.v.addItem(line)
                    self._pcb_model_items.append(line)
                    label = GLTextItem(
                        pos=np.asarray(label_pos, dtype=float),
                        color=QColor.fromRgbF(*PCB_MODEL_PICK_INSPECTION_TEXT_COLOR),
                        text=label_text,
                        font=QFont("Arial", 9),
                    )
                    label.setGLOptions("translucent")
                    self.v.addItem(label)
                    self._pcb_model_items.append(label)
                    self._pcb_model_label_items.append(label)
                self._update_pcb_label_lod()

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
                pcb_center = pcb.get("center") or [0.0, 0.0]
                component_base_z = BOARD_TOP_Z + thickness + 0.04
                for component in model.get("components") or []:
                    designator = str(component.get("designator", "") or "").strip().upper()
                    if designator not in board_components or (visible and designator not in visible):
                        continue
                    material = materials.get(designator) or {}
                    package = material.get("package") or component.get("package")
                    local_x, local_y = _pcb_model_local_xy(
                        component.get("x", 0.0),
                        component.get("y", 0.0),
                        pcb_center,
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
                    base_meshes = build_component_meshes(
                        package,
                        scale_x,
                        scale_y,
                        value=material.get("value") or component.get("value"),
                        rotation_degrees=base_angle,
                    )
                    for vertices, faces, color in base_meshes:
                        released_color = (
                            float(color[0]),
                            float(color[1]),
                            float(color[2]),
                            float(color[3]) * RELEASED_COMPONENT_ALPHA,
                        ) if released else color
                        mesh_class = GLMeshItem if released else SolidGLMeshItem
                        mesh = mesh_class(
                            meshdata=pg.opengl.MeshData(vertexes=vertices, faces=faces),
                            color=released_color,
                            smooth=False,
                            shader="shaded",
                            glOptions="translucent" if released else "opaque",
                        )
                        mesh.translate(base_x, base_y, component_base_z)
                        self.v.addItem(mesh)
                        if inspection.get("found", False):
                            mesh.setVisible(False)
                        self._pcb_model_items.append(mesh)

                    inspect_x, inspect_y, inspect_angle = _pcb_model_inspection_adjustment(
                        state, designator
                    )
                    if not inspection.get("found", False):
                        continue
                    for vertices, faces, color in build_component_meshes(
                        package,
                        scale_x,
                        scale_y,
                        value=material.get("value") or component.get("value"),
                        rotation_degrees=nominal_angle + inspect_angle,
                    ):
                        mesh = SolidGLMeshItem(
                            meshdata=pg.opengl.MeshData(vertexes=vertices, faces=faces),
                            color=color,
                            smooth=False,
                            shader="shaded",
                            glOptions="opaque",
                        )
                        mesh.translate(
                            nominal_x + inspect_x,
                            nominal_y + inspect_y,
                            component_base_z + 0.08,
                        )
                        self.v.addItem(mesh)
                        self._pcb_model_items.append(mesh)

                held = _pcb_model_held_component(model, state)
                if held:
                    nozzle = held["nozzle"]
                    tool_x, tool_y = self._tool_offsets.get(nozzle, (0.0, 0.0))
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
                    tip_z = float(self._model_pose[2]) + float(
                        self._nozzle_z_applied.get(nozzle, 0.0)
                    )
                    held_base_z = (
                        tip_z - component_height - NOZZLE_CONTACT_CLEARANCE
                    )
                    for vertices, faces, color in meshes:
                        mesh = SolidGLMeshItem(
                            meshdata=pg.opengl.MeshData(vertexes=vertices, faces=faces),
                            color=color,
                            smooth=False,
                            shader="shaded",
                            glOptions="opaque",
                        )
                        mesh.translate(
                            float(self._model_pose[0]) + tool_x - held["contact_x"],
                            float(self._model_pose[1]) + tool_y - held["contact_y"],
                            held_base_z,
                        )
                        self.v.addItem(mesh)
                        mesh.setVisible(self._display_visibility["pick_top_camera"])
                        self._pcb_model_items.append(mesh)
                        self._held_component_items.append(mesh)
                    self._held_component_nozzle = nozzle

                # PCB state coordinates are published in the H0 frame. If a
                # model is rebuilt while H is already non-zero, apply the
                # carriage displacement immediately to board-owned items only.
                if self._h_position:
                    held_ids = {id(item) for item in self._held_component_items}
                    for item in self._pcb_model_items:
                        if id(item) not in held_ids:
                            item.translate(float(self._h_position), 0.0, 0.0)

                self._pcb_model_revision = revision
                self._pcb_model_signature = signature
            except Exception as e:
                print(f"[Tel] 3D PCB model render failed: {e}")
                self.clear_pcb_model()

        def _add_machine_model(self):
            cyl_verts, cyl_faces = _mesh_cylinder()
            lens_top_verts, lens_top_faces = _mesh_cylinder(
                LENS_TOP_RADIUS,
                LENS_TOP_HEIGHT,
            )
            lens_block_verts, lens_block_faces = _mesh_box(
                LENS_BLOCK_SIZE,
                LENS_BLOCK_SIZE,
                LENS_BLOCK_HEIGHT,
            )
            ring_light_verts, ring_light_faces = _mesh_ring_cylinder(
                RING_LIGHT_INNER_RADIUS,
                RING_LIGHT_OUTER_RADIUS,
                RING_LIGHT_HEIGHT,
            )
            bottom_cyl_verts, bottom_cyl_faces = _mirror_mesh_z(cyl_verts, cyl_faces)
            bottom_lens_top_verts, bottom_lens_top_faces = _mirror_mesh_z(
                lens_top_verts,
                lens_top_faces,
            )
            bottom_lens_top_verts[:, 2] -= LENS_HEIGHT
            bottom_lens_block_verts, bottom_lens_block_faces = _mirror_mesh_z(
                lens_block_verts,
                lens_block_faces,
            )
            bottom_lens_block_verts[:, 2] -= LENS_HEIGHT + LENS_TOP_HEIGHT
            bottom_ring_light_verts, bottom_ring_light_faces = _mirror_mesh_z(
                ring_light_verts,
                ring_light_faces,
            )
            cone_verts, cone_faces = _mesh_inverted_cone()
            bottom1_link_verts, bottom1_link_faces = _mesh_cylinder(
                NOZZLE_BOTTOM1_LINK_RADIUS,
                NOZZLE_BOTTOM1_LINK_HEIGHT,
            )
            bottom2_link_verts, bottom2_link_faces = _mesh_cylinder(
                NOZZLE_BOTTOM2_LINK_RADIUS,
                NOZZLE_BOTTOM2_LINK_HEIGHT,
            )
            block_verts, block_faces = _mesh_box()
            top_link_verts, top_link_faces = _mesh_cylinder(
                NOZZLE_TOP_LINK_RADIUS,
                NOZZLE_TOP_LINK_HEIGHT,
            )
            cap_verts, cap_faces = _mesh_cylinder(
                NOZZLE_CAP_RADIUS,
                NOZZLE_CAP_HEIGHT,
            )
            marker_verts, marker_faces = _mesh_cylinder(
                CAMERA_MARKER_RADIUS,
                CAMERA_MARKER_HEIGHT,
            )
            top_marker_verts, top_marker_faces = _mirror_mesh_z(
                marker_verts,
                marker_faces,
            )
            top_marker_verts[:, 2] -= 0.02
            self._camera_marker_item = GLMeshItem(
                meshdata=pg.opengl.MeshData(vertexes=top_marker_verts, faces=top_marker_faces),
                color=CAMERA_MARKER_COLOR,
                smooth=False,
                shader="shaded",
                glOptions="opaque",
            )
            self._camera_marker_item.translate(
                float(self._model_pose[0]),
                float(self._model_pose[1]),
                float(self._model_pose[2]),
            )
            self.v.addItem(self._camera_marker_item)
            self._lens_item = GLMeshItem(
                meshdata=pg.opengl.MeshData(vertexes=cyl_verts, faces=cyl_faces),
                color=LENS_COLOR,
                smooth=False,
                shader="shaded",
                glOptions="opaque",
            )
            self._lens_item.translate(*self._model_pose)
            self.v.addItem(self._lens_item)
            self._ring_light_item = GLMeshItem(
                meshdata=pg.opengl.MeshData(vertexes=ring_light_verts, faces=ring_light_faces),
                color=RING_LIGHT_COLOR,
                smooth=False,
                shader="shaded",
                glOptions="opaque",
            )
            self._ring_light_item.translate(*self._model_pose)
            self.v.addItem(self._ring_light_item)
            self._top_ring_glow_items = []
            for layer_idx in range(RING_LIGHT_GLOW_LAYERS):
                inner_radius = RING_LIGHT_GLOW_INNER_RADIUS + layer_idx * (RING_LIGHT_GLOW_RADIUS_STEP * 0.45)
                outer_radius = RING_LIGHT_GLOW_OUTER_RADIUS + layer_idx * RING_LIGHT_GLOW_RADIUS_STEP
                glow_verts, glow_faces = _mesh_ring_cylinder(
                    inner_radius,
                    outer_radius,
                    RING_LIGHT_GLOW_HEIGHT,
                )
                # Top lamp emits downward: keep the complete emissive mesh
                # below the ring's bottom face instead of intersecting its body.
                glow_verts[:, 2] = (
                    -glow_verts[:, 2]
                    - (layer_idx + 1) * RING_LIGHT_GLOW_STEP
                )
                glow_item = DepthTestedGlowMeshItem(
                    meshdata=pg.opengl.MeshData(vertexes=glow_verts, faces=glow_faces),
                    color=(RING_LIGHT_GLOW_COLOR[0], RING_LIGHT_GLOW_COLOR[1], RING_LIGHT_GLOW_COLOR[2], 0.0),
                    smooth=False,
                    shader="shaded",
                    glOptions="additive",
                )
                glow_item.translate(*self._model_pose)
                glow_item.setVisible(False)
                self.v.addItem(glow_item)
                self._top_ring_glow_items.append(glow_item)
            self._lens_stack_items = []
            lens_stack_specs = [
                (lens_top_verts, lens_top_faces, LENS_COLOR, LENS_HEIGHT),
                (
                    lens_block_verts,
                    lens_block_faces,
                    LENS_COLOR,
                    LENS_HEIGHT + LENS_TOP_HEIGHT,
                ),
            ]
            for verts, faces, color, local_z in lens_stack_specs:
                lens_part = GLMeshItem(
                    meshdata=pg.opengl.MeshData(vertexes=verts, faces=faces),
                    color=color,
                    smooth=False,
                    shader="shaded",
                    glOptions="opaque",
                )
                lens_part.translate(
                    float(self._model_pose[0]),
                    float(self._model_pose[1]),
                    float(self._model_pose[2] + local_z),
                )
                self.v.addItem(lens_part)
                self._lens_stack_items.append(lens_part)
            self._bottom_camera_items = []
            self._bottom_camera_marker_item = GLMeshItem(
                meshdata=pg.opengl.MeshData(
                    vertexes=marker_verts,
                    faces=marker_faces,
                ),
                color=CAMERA_MARKER_COLOR,
                smooth=False,
                shader="shaded",
                glOptions="opaque",
            )
            self.v.addItem(self._bottom_camera_marker_item)
            self._bottom_camera_marker_item.setVisible(False)
            self._bottom_camera_items.append(self._bottom_camera_marker_item)
            bottom_camera_specs = [
                (bottom_cyl_verts, bottom_cyl_faces, LENS_COLOR, False),
                (bottom_ring_light_verts, bottom_ring_light_faces, RING_LIGHT_COLOR, False),
                (bottom_lens_top_verts, bottom_lens_top_faces, LENS_COLOR, False),
                (bottom_lens_block_verts, bottom_lens_block_faces, LENS_COLOR, False),
            ]
            for verts, faces, color, smooth in bottom_camera_specs:
                item = GLMeshItem(
                    meshdata=pg.opengl.MeshData(vertexes=verts, faces=faces),
                    color=color,
                    smooth=smooth,
                    shader="shaded",
                    glOptions="opaque",
                )
                self.v.addItem(item)
                item.setVisible(False)
                self._bottom_camera_items.append(item)
            self._bottom_ring_glow_items = []
            for layer_idx in range(RING_LIGHT_GLOW_LAYERS):
                inner_radius = RING_LIGHT_GLOW_INNER_RADIUS + layer_idx * (RING_LIGHT_GLOW_RADIUS_STEP * 0.45)
                outer_radius = RING_LIGHT_GLOW_OUTER_RADIUS + layer_idx * RING_LIGHT_GLOW_RADIUS_STEP
                glow_verts, glow_faces = _mesh_ring_cylinder(
                    inner_radius,
                    outer_radius,
                    RING_LIGHT_GLOW_HEIGHT,
                )
                glow_verts[:, 2] += (layer_idx + 1) * RING_LIGHT_GLOW_STEP
                glow_item = DepthTestedGlowMeshItem(
                    meshdata=pg.opengl.MeshData(vertexes=glow_verts, faces=glow_faces),
                    color=(RING_LIGHT_GLOW_COLOR[0], RING_LIGHT_GLOW_COLOR[1], RING_LIGHT_GLOW_COLOR[2], 0.0),
                    smooth=False,
                    shader="shaded",
                    glOptions="additive",
                )
                glow_item.setVisible(False)
                self.v.addItem(glow_item)
                self._bottom_ring_glow_items.append(glow_item)
            connector_verts, connector_faces = _mesh_box(
                HEAD_CONNECTOR_X,
                HEAD_CONNECTOR_Y,
                HEAD_CONNECTOR_Z,
            )
            rail_verts, rail_faces = _mesh_box(
                GUIDE_RAIL_X,
                GUIDE_RAIL_Y,
                GUIDE_RAIL_Z,
            )
            self._head_connector_items = []
            for verts, faces, color in (
                (connector_verts, connector_faces, DEEP_SILVER_COLOR),
                (connector_verts, connector_faces, DEEP_SILVER_COLOR),
                (rail_verts, rail_faces, METAL_SILVER_COLOR),
                (rail_verts, rail_faces, METAL_SILVER_COLOR),
            ):
                item = GLMeshItem(
                    meshdata=pg.opengl.MeshData(vertexes=verts, faces=faces),
                    color=color,
                    smooth=False,
                    shader="shaded",
                    glOptions="opaque",
                )
                item.translate(*self._model_pose)
                self.v.addItem(item)
                item.setVisible(False)
                self._head_connector_items.append(item)
            self._head_connector_local_applied = [
                np.zeros(3, dtype=float),
                np.zeros(3, dtype=float),
                np.zeros(3, dtype=float),
                np.zeros(3, dtype=float),
            ]
            self._head_connector_z_applied = [0.0, 0.0]
            self._head_extra_items = []
            self._head_extra_local_applied = []
            self._head_extra_dims = []
            self._nozzle_items = {}
            self._nozzle_stack_items = {}
            stack_specs = [
                (bottom1_link_verts, bottom1_link_faces, METAL_SILVER_COLOR, 0.0),
                (
                    bottom2_link_verts,
                    bottom2_link_faces,
                    BRASS_COLOR,
                    NOZZLE_BOTTOM1_LINK_HEIGHT,
                ),
                (block_verts, block_faces, DARK_BLOCK_COLOR, NOZZLE_BOTTOM_LINK_HEIGHT),
                (
                    top_link_verts,
                    top_link_faces,
                    BRASS_COLOR,
                    NOZZLE_BOTTOM_LINK_HEIGHT + NOZZLE_BLOCK_HEIGHT,
                ),
                (
                    cap_verts,
                    cap_faces,
                    LIGHT_CAP_COLOR,
                    NOZZLE_BOTTOM_LINK_HEIGHT + NOZZLE_BLOCK_HEIGHT + NOZZLE_TOP_LINK_HEIGHT,
                ),
            ]
            for key in ("pl", "pr"):
                cone_item = GLMeshItem(
                    meshdata=pg.opengl.MeshData(vertexes=cone_verts, faces=cone_faces),
                    color=NOZZLE_COLOR,
                    smooth=False,
                    shader="shaded",
                    glOptions="opaque",
                )
                cone_item.translate(
                    float(self._model_pose[0]),
                    float(self._model_pose[1]),
                    float(self._model_pose[2] + NOZZLE_HEIGHT),
                )
                self.v.addItem(cone_item)
                cone_item.setVisible(False)
                self._nozzle_items[key] = cone_item

                self._nozzle_stack_items[key] = []
                for verts, faces, color, local_z in stack_specs:
                    part = GLMeshItem(
                        meshdata=pg.opengl.MeshData(vertexes=verts, faces=faces),
                        color=color,
                        smooth=False,
                        shader="shaded",
                        glOptions="opaque",
                    )
                    part.translate(
                        float(self._model_pose[0]),
                        float(self._model_pose[1]),
                        float(self._model_pose[2] + NOZZLE_HEIGHT + local_z),
                    )
                    self.v.addItem(part)
                    part.setVisible(False)
                    self._nozzle_stack_items[key].append(part)
            self._update_ring_light_glow_items()

        def _move_machine_model(self, x, y, z, balance_z):
            base_pose = np.array([x, y, float(balance_z)], dtype=float)
            delta = base_pose - self._model_pose
            if not np.any(delta):
                delta = np.zeros(3, dtype=float)
            # Resolve all collision constraints before mutating any GL item.
            # A failed calculation must never leave the articulated model half-moved.
            z_offsets = _nozzle_visual_z_offsets(self._tool_offsets, z, balance_z)
            z_offsets = _clamp_nozzle_z_offsets(
                self._tool_offsets,
                z_offsets,
                x,
                y,
                balance_z,
                self._feeder_inventory,
                self._feeder_item_pos,
                self._component_scale,
                self._pcb_model_state,
                self._pcb_model_data,
            )
            self._camera_marker_item.translate(float(delta[0]), float(delta[1]), float(delta[2]))
            self._lens_item.translate(float(delta[0]), float(delta[1]), float(delta[2]))
            self._ring_light_item.translate(float(delta[0]), float(delta[1]), float(delta[2]))
            for item in self._top_ring_glow_items:
                item.translate(float(delta[0]), float(delta[1]), float(delta[2]))
            for item in self._lens_stack_items:
                item.translate(float(delta[0]), float(delta[1]), float(delta[2]))
            for item in self._head_connector_items:
                item.translate(float(delta[0]), float(delta[1]), float(delta[2]))
            for item in self._head_extra_items:
                item.translate(float(delta[0]), float(delta[1]), float(delta[2]))
            for idx, key in enumerate(("pl", "pr")):
                target_z = z_offsets.get(key, 0.0)
                dz_conn = target_z - self._head_connector_z_applied[idx]
                if dz_conn and idx < len(self._head_connector_items):
                    self._head_connector_items[idx].translate(0.0, 0.0, float(dz_conn))
                self._head_connector_z_applied[idx] = target_z
            for key, item in self._nozzle_items.items():
                target_nozzle_z = z_offsets.get(key, 0.0)
                nozzle_dz = target_nozzle_z - self._nozzle_z_applied.get(key, 0.0)
                item.translate(float(delta[0]), float(delta[1]), float(delta[2] + nozzle_dz))
                for part in self._nozzle_stack_items.get(key, []):
                    part.translate(float(delta[0]), float(delta[1]), float(delta[2] + nozzle_dz))
                if key == self._held_component_nozzle:
                    for held_item in self._held_component_items:
                        held_item.translate(
                            float(delta[0]),
                            float(delta[1]),
                            float(delta[2] + nozzle_dz),
                        )
                self._nozzle_z_applied[key] = target_nozzle_z
            self._model_pose = base_pose

        def _update_ring_light_glow_items(self):
            for name, items in (
                ("top", getattr(self, "_top_ring_glow_items", [])),
                ("bottom", getattr(self, "_bottom_ring_glow_items", [])),
            ):
                level = self._ring_light_levels.get(name, 0)
                if not items:
                    continue
                active_layers = (
                    max(1, min(len(items), int(math.ceil(level / (100.0 / len(items))))))
                    if level > 0
                    else 0
                )
                alpha_scale = math.pow(level / 100.0, 0.55) if level > 0 else 0.0
                for idx, item in enumerate(items):
                    visible = idx < active_layers and (
                        name != "bottom" or getattr(self, "_bottom_camera_origin", None) is not None
                    )
                    visible = visible and self._display_visibility[
                        "pick_top_camera" if name == "top" else "bottom_camera"
                    ]
                    item.setVisible(visible)
                    if not visible:
                        continue
                    layer_fade = 1.0 - (idx / max(1, len(items)))
                    alpha = RING_LIGHT_GLOW_MIN_ALPHA + (
                        (RING_LIGHT_GLOW_MAX_ALPHA - RING_LIGHT_GLOW_MIN_ALPHA)
                        * alpha_scale
                        * layer_fade
                    )
                    alpha *= self._demo_group_opacity(
                        self._demo_emphasis[0],
                        "top_camera" if name == "top" else "bottom_camera",
                        active_nozzle=self._demo_emphasis[1],
                    )
                    self._apply_mesh_color(
                        item,
                        (
                            RING_LIGHT_GLOW_COLOR[0],
                            RING_LIGHT_GLOW_COLOR[1],
                            RING_LIGHT_GLOW_COLOR[2],
                            alpha,
                        ),
                    )

        def _update_head_connector_items(self):
            poses = _head_connector_local_poses(self._tool_offsets)
            if not poses:
                return
            locals_new = [
                np.array(poses["connectors"][0], dtype=float),
                np.array(poses["connectors"][1], dtype=float),
                np.array(poses["rails"][0], dtype=float),
                np.array(poses["rails"][1], dtype=float),
            ]
            for item, old_local, new_local in zip(
                self._head_connector_items,
                self._head_connector_local_applied,
                locals_new,
            ):
                delta = new_local - old_local
                if np.any(delta):
                    item.translate(float(delta[0]), float(delta[1]), float(delta[2]))
                item.setVisible(self._display_visibility["pick_top_camera"])
            self._head_connector_local_applied = locals_new
            self._update_head_extra_items(poses)

        def _update_head_extra_items(self, poses):
            extra_specs = [
                (poses["frame"], METAL_SILVER_COLOR),
                (poses["camera_link"], METAL_SILVER_COLOR),
            ]
            if not self._head_extra_items:
                for pose, color in extra_specs:
                    lx, ly, lz, sx, sy, sz = pose
                    verts, faces = _mesh_box(sx, sy, sz)
                    item = GLMeshItem(
                        meshdata=pg.opengl.MeshData(vertexes=verts, faces=faces),
                        color=color,
                        smooth=False,
                        shader="shaded",
                        glOptions="opaque",
                    )
                    item.translate(
                        float(self._model_pose[0] + lx),
                        float(self._model_pose[1] + ly),
                        float(self._model_pose[2] + lz),
                    )
                    self.v.addItem(item)
                    item.setVisible(self._display_visibility["pick_top_camera"])
                    self._head_extra_items.append(item)
                    self._head_extra_local_applied.append(np.array([lx, ly, lz], dtype=float))
                    self._head_extra_dims.append((sx, sy, sz))
                return
            for idx, (pose, _color) in enumerate(extra_specs):
                lx, ly, lz, sx, sy, sz = pose
                dims = (sx, sy, sz)
                new_local = np.array([lx, ly, lz], dtype=float)
                if self._head_extra_dims[idx] != dims:
                    # Size changes are rare (calibration changed); rebuild the solid box.
                    old_item = self._head_extra_items[idx]
                    old_item.setVisible(False)
                    try:
                        self.v.removeItem(old_item)
                    except Exception:
                        pass
                    verts, faces = _mesh_box(sx, sy, sz)
                    item = GLMeshItem(
                        meshdata=pg.opengl.MeshData(vertexes=verts, faces=faces),
                        color=extra_specs[idx][1],
                        smooth=False,
                        shader="shaded",
                        glOptions="opaque",
                    )
                    item.translate(
                        float(self._model_pose[0] + lx),
                        float(self._model_pose[1] + ly),
                        float(self._model_pose[2] + lz),
                    )
                    self.v.addItem(item)
                    item.setVisible(self._display_visibility["pick_top_camera"])
                    self._head_extra_items[idx] = item
                    self._head_extra_local_applied[idx] = new_local
                    self._head_extra_dims[idx] = dims
                    continue
                delta = new_local - self._head_extra_local_applied[idx]
                if np.any(delta):
                    self._head_extra_items[idx].translate(
                        float(delta[0]),
                        float(delta[1]),
                        float(delta[2]),
                    )
                self._head_extra_items[idx].setVisible(
                    self._display_visibility["pick_top_camera"]
                )
                self._head_extra_local_applied[idx] = new_local

        def _add_board(self, bounds=None):
            """Add a rectangular PCB board cuboid with a dark 9x9 top grid."""
            for item in getattr(self, "_board_geometry_items", []):
                try:
                    self.v.removeItem(item)
                except Exception:
                    pass
                try:
                    self._workdesk_items.remove(item)
                except ValueError:
                    pass
            self._board_geometry_items = []
            # Original four locating points. Do not mutate these; drawing uses expanded copies only.
            if bounds:
                min_x = float(bounds["x_min"])
                max_x = float(bounds["x_max"])
                min_y = float(bounds["y_min"])
                max_y = float(bounds["y_max"])
                anchor_top = np.array(
                    [
                        [min_x, min_y, BOARD_TOP_Z],
                        [max_x, min_y, BOARD_TOP_Z],
                        [max_x, max_y, BOARD_TOP_Z],
                        [min_x, max_y, BOARD_TOP_Z],
                    ],
                    dtype=float,
                )
            else:
                anchor_top = np.array([
                    [143.38, 72.48, BOARD_TOP_Z],   # BR
                    [274.17, 72.70, BOARD_TOP_Z],   # TR
                    [274.65, 201.97, BOARD_TOP_Z],  # TL
                    [143.68, 202.02, BOARD_TOP_Z],  # BL
                ], dtype=float)
            anchor_top[:, 0] += self._h_position
            min_x = float(anchor_top[:, 0].min())
            max_x = float(anchor_top[:, 0].max())
            min_y = float(anchor_top[:, 1].min())
            max_y = float(anchor_top[:, 1].max())
            board_w = max_x - min_x
            board_d = max_y - min_y
            board_center_x = (min_x + max_x) / 2.0
            board_center_y = (min_y + max_y) / 2.0
            verts, faces = _mesh_box(board_w, board_d, BOARD_TOP_Z)
            verts[:, 0] += board_center_x
            verts[:, 1] += board_center_y
            top = np.array([
                [min_x, min_y, BOARD_TOP_Z],
                [max_x, min_y, BOARD_TOP_Z],
                [max_x, max_y, BOARD_TOP_Z],
                [min_x, max_y, BOARD_TOP_Z],
            ], dtype=float)
            # Original anchor reference (kept for future locating/debug use)
            self._board_anchor_verts = np.vstack([
                np.array([
                    [143.38, 72.48, 0.0],
                    [274.17, 72.70, 0.0],
                    [274.65, 201.97, 0.0],
                    [143.68, 202.02, 0.0],
                ], dtype=float),
                anchor_top,
            ])
            # 12 triangle faces (6 quads → 2 triangles each)
            md = pg.opengl.MeshData(vertexes=verts, faces=faces)
            mesh = SolidGLMeshItem(meshdata=md, color=BOARD_DARK_COLOR,
                              smooth=False, shader='balloon', glOptions='opaque')
            self.v.addItem(mesh)
            self._workdesk_items.append(mesh)
            self._board_geometry_items.append(mesh)
            strip_z = BOARD_TOP_Z + 0.01
            strip_w = BOARD_GRID_STRIP_WIDTH
            strip_h = BOARD_GRID_STRIP_HEIGHT
            grid_specs = []
            for i in range(10):
                t = i / 9.0
                x = top[0][0] + (top[1][0] - top[0][0]) * t
                y = top[0][1] + (top[3][1] - top[0][1]) * t
                grid_specs.append((x, board_center_y, strip_w, board_d, strip_z))
                grid_specs.append((board_center_x, y, board_w, strip_w, strip_z))
            for cx, cy, width, depth, z0 in grid_specs:
                gverts, gfaces = _mesh_box(width, depth, strip_h)
                gverts[:, 0] += cx
                gverts[:, 1] += cy
                gverts[:, 2] += z0
                gmd = pg.opengl.MeshData(vertexes=gverts, faces=gfaces)
                grid = SolidGLMeshItem(
                    meshdata=gmd,
                    color=BOARD_GRID_COLOR,
                    smooth=False,
                    shader='balloon',
                    glOptions='opaque',
                )
                self.v.addItem(grid)
                self._workdesk_items.append(grid)
                self._board_geometry_items.append(grid)
