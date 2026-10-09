"""Preview backend for JanPNP live 3D and parameter views."""
import json
import base64
import math
import threading
import time

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QFrame, QMainWindow, QAction)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QFont, QImage, QMatrix4x4, QVector3D

import pyqtgraph as pg
import numpy as np
from depends.pnp_models import *
from depends.component_models import (
    FEEDER_TAPE_HEIGHT,
    build_component_meshes,
    feeder_tape_color,
    get_package_definition,
    pcb_component_rotation,
)

PG_OK = True
NOZZLE_CONTACT_CLEARANCE = 0.03
RELEASED_COMPONENT_ALPHA = 0.55


def _inspection_label_lod(camera_distance, index):
    """Map-style label sizing and decluttering for PCB inspection text."""
    distance = max(1.0, float(camera_distance or 400.0))
    if distance <= 350.0:
        return 10
    if distance <= 500.0:
        return 8
    if distance <= 650.0:
        return 7 if index % 2 == 0 else None
    return None


def _inside_rect(x, y, center_x, center_y, width_x, width_y):
    return (
        abs(float(x) - float(center_x)) <= float(width_x) / 2.0
        and abs(float(y) - float(center_y)) <= float(width_y) / 2.0
    )


def _boost_color(color, factor=1.75):
    return (
        min(1.0, float(color[0]) * factor),
        min(1.0, float(color[1]) * factor),
        min(1.0, float(color[2]) * factor),
        float(color[3]),
    )


def _contact_surface_z(
    x,
    y,
    feeder_inventory,
    feeder_origins,
    component_scale,
    pcb_state,
    pcb_model,
):
    """Return the highest solid work surface below a nozzle at scene X/Y."""
    surface = None
    tape_top = (
        BOARD_TOP_Z
        - FEEDER_SLOT_DEPTH
        - FEEDER_SLOT_RECESS
        + FEEDER_SLOT_FLOOR
        + FEEDER_TAPE_HEIGHT
    )
    sx = abs(float((component_scale or {}).get("x", 1.0) or 1.0))
    sy = abs(float((component_scale or {}).get("y", 1.0) or 1.0))
    for material in feeder_inventory or []:
        slot = str(material.get("slot", "")).upper()
        feeder_origin = (feeder_origins or {}).get(slot)
        if feeder_origin is not None and len(feeder_origin) >= 2 and _inside_rect(
            x,
            y,
            feeder_origin[0],
            feeder_origin[1],
            FEEDER_SLOT_X - 2.0 * FEEDER_SLOT_WALL,
            FEEDER_SLOT_Y - 2.0 * FEEDER_SLOT_WALL,
        ):
            surface = tape_top if surface is None else max(surface, tape_top)
        center = material.get("center_jp") or {}
        spec = get_package_definition(material.get("package"))
        if not spec:
            continue
        try:
            component_x = float(center["x"])
            component_y = float(center["y"])
        except (KeyError, TypeError, ValueError):
            continue
        # Feeder parts are rotated 90 degrees: package width maps to scene X.
        footprint_x = max(1.0, spec.width * sx)
        footprint_y = max(1.0, spec.length * sy)
        if _inside_rect(
            x, y, component_x, component_y, footprint_x, footprint_y
        ):
            component_top = tape_top + float(spec.height)
            surface = component_top if surface is None else max(surface, component_top)

    state = pcb_state or {}
    model = pcb_model or {}
    if state.get("active") and model:
        pcb = model.get("pcb") or {}
        size = pcb.get("size_mm") or {}
        pose = state.get("center_jp") or {}
        scale = state.get("scale_jp_per_mm") or {}
        try:
            pcb_x = float(pose["x"])
            pcb_y = float(pose["y"])
            depth_x = float(size.get("height", 0.0)) * abs(
                float(scale.get("x", 1.0) or 1.0)
            )
            width_y = float(size.get("width", 0.0)) * abs(
                float(scale.get("y", 1.0) or 1.0)
            )
            thickness = max(0.05, float(state.get("thickness", 0.5) or 0.5))
            if depth_x > 0.0 and width_y > 0.0 and _inside_rect(
                x, y, pcb_x, pcb_y, depth_x, width_y
            ):
                pcb_top = BOARD_TOP_Z + thickness
                surface = pcb_top if surface is None else max(surface, pcb_top)
        except (KeyError, TypeError, ValueError):
            pass
    return surface


def _clamp_nozzle_z_offsets(
    tool_offsets,
    z_offsets,
    machine_x,
    machine_y,
    balance_z,
    feeder_inventory,
    feeder_origins,
    component_scale,
    pcb_state,
    pcb_model,
):
    result = dict(z_offsets or {})
    held = _pcb_model_held_component(pcb_model, pcb_state)
    held_height = 0.0
    if held:
        held_meshes = build_component_meshes(held["package"])
        held_height = max(
            (
                float(vertices[:, 2].max())
                for vertices, _faces, _color in held_meshes
            ),
            default=0.0,
        )
    for key, offset in (tool_offsets or {}).items():
        nozzle_x = float(machine_x) + float(offset[0])
        nozzle_y = float(machine_y) + float(offset[1])
        surface = _contact_surface_z(
            nozzle_x,
            nozzle_y,
            feeder_inventory,
            feeder_origins,
            component_scale,
            pcb_state,
            pcb_model,
        )
        if surface is None:
            continue
        component_clearance = held_height if held and held["nozzle"] == key else 0.0
        minimum_offset = (
            float(surface)
            + component_clearance
            + NOZZLE_CONTACT_CLEARANCE
            - float(balance_z)
        )
        result[key] = max(float(result.get(key, 0.0)), minimum_offset)
    return result

try:
    from pyqtgraph.opengl import (
        GLGridItem,
        GLLinePlotItem,
        GLMeshItem,
        GLScatterPlotItem,
        GLTextItem,
        GLViewWidget,
    )
    from pyqtgraph.opengl import shaders as _pg_shaders
    try:
        from pyqtgraph.opengl import GLImageItem
    except Exception:
        GLImageItem = None
    from OpenGL import GL as _GL
    GL_OK = True
    GL_BACKEND = "pyqtgraph"

    if FEEDER_SHADER not in _pg_shaders.ShaderProgram.names:
        _pg_shaders.ShaderProgram(
            FEEDER_SHADER,
            [
                _pg_shaders.VertexShader("""
                    uniform mat4 u_mvp;
                    uniform mat3 u_normal;
                    attribute vec4 a_position;
                    attribute vec3 a_normal;
                    attribute vec4 a_color;
                    varying vec4 v_color;
                    varying vec3 v_normal;
                    void main() {
                        v_normal = normalize(u_normal * a_normal);
                        v_color = a_color;
                        gl_Position = u_mvp * a_position;
                    }
                """),
                _pg_shaders.FragmentShader("""
                    #ifdef GL_ES
                    precision mediump float;
                    #endif
                    varying vec4 v_color;
                    varying vec3 v_normal;
                    void main() {
                        float diffuse = max(
                            dot(v_normal, normalize(vec3(1.0, -1.0, -1.0))),
                            0.0
                        );
                        vec3 rgb = v_color.rgb * (0.46 + diffuse * 0.54);
                        gl_FragColor = vec4(rgb, v_color.a);
                    }
                """),
            ],
        )

    class SolidGLMeshItem(GLMeshItem):
        def setupGLState(self):
            super().setupGLState()
            if getattr(self, "_demo_translucent", False):
                _GL.glEnable(_GL.GL_BLEND)
                _GL.glBlendFunc(_GL.GL_SRC_ALPHA, _GL.GL_ONE_MINUS_SRC_ALPHA)
                _GL.glDepthMask(_GL.GL_FALSE)
            else:
                _GL.glDisable(_GL.GL_BLEND)
                _GL.glDepthMask(_GL.GL_TRUE)
            _GL.glEnable(_GL.GL_DEPTH_TEST)

        def paint(self):
            try:
                super().paint()
            finally:
                _GL.glDepthMask(_GL.GL_TRUE)

    class DepthTestedGlowMeshItem(GLMeshItem):
        """Additive glow that remains occluded by opaque machine geometry."""

        def setupGLState(self):
            super().setupGLState()
            _GL.glEnable(_GL.GL_DEPTH_TEST)
            _GL.glDepthMask(_GL.GL_FALSE)

        def paint(self):
            try:
                super().paint()
            finally:
                _GL.glDepthMask(_GL.GL_TRUE)

except Exception:
    try:
        from PyQt5.QtOpenGL import QGLWidget
        from OpenGL.GL import *
        from OpenGL.GLU import *
        GL_OK = True
        GL_BACKEND = "qgl"
    except Exception:
        GL_OK = False
        GL_BACKEND = None


class Fetcher(threading.Thread):
    def __init__(self, url, pi_url="http://192.168.3.13:8080"):
        super().__init__(daemon=True)
        self.url = url; self.auth_url = pi_url + "/api/login"; self.settings_url = pi_url + "/api/settings"
        self.running = False; self.data = {}
        self.tool_offsets = None
        self.balance_z = DEFAULT_BALANCE_Z
        self.visit_2cam = None
        self.feeder_origins = dict(DEFAULT_FEEDERS_ORIGIN)
        self.active_feeders = set()
        self.feeder_inventory = []
        self.component_scale = {"x": 1.0, "y": 1.0}
        self.h_scene_scale = 1.0
        self.pcb_model_state = None
        self.pcb_model_data = None
        self.pcb_model_preview = None
        self._pcb_model_revision = None
        self._lock = threading.Lock(); self._cookie = None

    def set_cookie(self, cookie):
        self._cookie = cookie

    def _login(self):
        try:
            import urllib.request as R
            req = R.Request(self.auth_url,
                data=json.dumps({"username":"janpnp","password":"admin123"}).encode(),
                headers={"Content-Type":"application/json"})
            resp = R.urlopen(req, timeout=3)
            self._cookie = resp.headers.get("Set-Cookie", "")
            return True
        except Exception as e:
            print(f"[Tel] Login: {e}"); return False

    def _fetch_settings(self, opener):
        try:
            raw = opener.urlopen(
                opener.Request(self.settings_url, headers={"Cookie": self._cookie or ""}),
                timeout=3,
            ).read()
            settings = json.loads(raw)
            offsets = _tool_offsets_from_settings(settings)
            balance_z = _balance_z_from_settings(settings)
            visit_2cam = _visit_2cam_from_settings(settings)
            with self._lock:
                self.balance_z = balance_z
                if visit_2cam:
                    self.visit_2cam = visit_2cam
                self.feeder_origins = dict(DEFAULT_FEEDERS_ORIGIN)
                if offsets:
                    self.tool_offsets = offsets
        except Exception as e:
            print(f"[Tel] Settings: {e}")

    def _fetch_pcb_model(self, opener, state):
        if not state or not state.get("active"):
            with self._lock:
                self.pcb_model_state = state
                self.pcb_model_data = None
                self.pcb_model_preview = None
                self._pcb_model_revision = state.get("revision") if state else None
            return
        revision = state.get("revision")
        with self._lock:
            if revision == self._pcb_model_revision and self.pcb_model_data is not None:
                self.pcb_model_state = dict(state)
                return
        model_url = str(state.get("model_url") or "")
        if not model_url:
            return
        if model_url.startswith("http://") or model_url.startswith("https://"):
            url = model_url
        else:
            url = self.auth_url.rsplit("/api/login", 1)[0].rstrip("/") + model_url
        try:
            raw = opener.urlopen(
                opener.Request(url, headers={"Cookie": self._cookie or ""}),
                timeout=3,
            ).read()
            model = json.loads(raw)
            preview = self._fetch_pcb_preview(opener, state, model)
            with self._lock:
                self.pcb_model_state = dict(state)
                self.pcb_model_data = model
                self.pcb_model_preview = preview
                self._pcb_model_revision = revision
        except Exception as e:
            print(f"[Tel] PCB model: {e}")

    def _image_bytes_to_array(self, raw, max_edge=4096):
        image = QImage()
        if not image.loadFromData(raw):
            return None
        if max(image.width(), image.height()) > max_edge:
            image = image.scaled(
                max_edge,
                max_edge,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        image = image.convertToFormat(QImage.Format_RGBA8888)
        width = image.width()
        height = image.height()
        ptr = image.bits()
        ptr.setsize(image.byteCount())
        arr = np.frombuffer(ptr, np.uint8).reshape((height, width, 4)).copy()
        cyan_mask = (arr[:, :, 0] < 90) & (arr[:, :, 1] > 130) & (arr[:, :, 2] > 130)
        if np.any(cyan_mask):
            body_rgb = np.array(
                [int(PCB_MODEL_BODY_COLOR[i] * 255) for i in range(3)],
                dtype=np.uint8,
            )
            arr[cyan_mask, :3] = body_rgb
        # Keep the image axes intact. GLImageItem maps the first array axis to
        # scene X and the second to scene Y; with our board dimensions this maps
        # preview height -> local X and preview width -> local Y. Flip both axes
        # to apply the required 180-degree board rotation without mirroring text.
        return np.flip(arr, axis=(0, 1)).copy()

    def _fetch_pcb_preview(self, opener, state, model):
        preview_url = str((state or {}).get("preview_url") or "")
        if not preview_url:
            order_id = str((state or {}).get("order_id") or "")
            if order_id:
                preview_url = f"/storage/order/{order_id}/preview.png"
        if not preview_url:
            return None
        if preview_url.startswith("http://") or preview_url.startswith("https://"):
            url = preview_url
        else:
            url = self.auth_url.rsplit("/api/login", 1)[0].rstrip("/") + preview_url
        try:
            raw = opener.urlopen(
                opener.Request(url, headers={"Cookie": self._cookie or ""}),
                timeout=3,
            ).read()
            return self._image_bytes_to_array(raw)
        except Exception as e:
            print(f"[Tel] PCB preview: {e}")
            return None

    def run(self):
        self.running = True
        if not self._login(): print("[Tel] Auth failed")
        import urllib.request as R
        last_settings = 0.0
        while self.running:
            try:
                now = time.time()
                if now - last_settings >= 5.0:
                    self._fetch_settings(R)
                    last_settings = now
                raw = R.urlopen(R.Request(self.url, headers={"Cookie":self._cookie or ""}), timeout=2).read()
                d = json.loads(raw).get("latest", {})
                if d:
                    active_feeders = _active_feeder_keys_from_telemetry(d)
                    pcb_state = d.get("pcb_model")
                    self._fetch_pcb_model(R, pcb_state)
                    with self._lock:
                        self.data = d
                        self.active_feeders = active_feeders
                        self.feeder_inventory = list(d.get("feeder_inventory") or [])
                        scale = d.get("component_scale_jp_per_mm") or {}
                        self.component_scale = {
                            "x": abs(float(scale.get("x", 1.0) or 1.0)),
                            "y": abs(float(scale.get("y", 1.0) or 1.0)),
                        }
                        self.h_scene_scale = self.component_scale["x"]
            except Exception as e:
                print(f"[Tel] Fetch: {e}")
            time.sleep(0.02)

    def get(self):
        with self._lock:
            return dict(self.data) if self.data else {}

    def get_tool_offsets(self):
        with self._lock:
            return dict(self.tool_offsets) if self.tool_offsets else None

    def get_balance_z(self):
        with self._lock:
            return self.balance_z

    def get_visit_2cam(self):
        with self._lock:
            return tuple(self.visit_2cam) if self.visit_2cam else None

    def get_feeders(self):
        with self._lock:
            return dict(self.feeder_origins), set(self.active_feeders)

    def get_feeder_inventory(self):
        with self._lock:
            return (
                [
                    dict(item)
                    for item in self.feeder_inventory
                    if str(item.get("slot", "")).upper() in self.active_feeders
                ],
                dict(self.component_scale),
            )

    def get_h_scene_scale(self):
        with self._lock:
            return float(self.h_scene_scale)

    def get_pcb_model(self):
        with self._lock:
            state = dict(self.pcb_model_state) if self.pcb_model_state else None
            data = dict(self.pcb_model_data) if self.pcb_model_data else None
            preview = self.pcb_model_preview
            return state, data, preview

    def clear_pcb_model_cache(self):
        with self._lock:
            self.pcb_model_state = None
            self.pcb_model_data = None
            self.pcb_model_preview = None
            self._pcb_model_revision = None


if GL_BACKEND == "pyqtgraph":
    try:
        from .preview_gl_pyqtgraph import GLW3D
    except ImportError:
        from preview_gl_pyqtgraph import GLW3D
else:
    try:
        from .preview_gl_qgl import GLW3D
    except ImportError:
        from preview_gl_qgl import GLW3D

class TelemetryWindow(QMainWindow):
    def __init__(self, pi_url="http://192.168.3.13:8080", embedded=False):
        super().__init__()
        self.pi_url = pi_url; self._busy = False
        self.max = 300
        self.t, self.px, self.py, self.pz = [deque(maxlen=self.max) for _ in range(4)]
        self.vx, self.vy, self.vz = [deque(maxlen=self.max) for _ in range(3)]
        self.tx, self.ty, self.tz = [deque(maxlen=6000) for _ in range(3)]  # up to 300s trail
        self._trail_visible = False   # off by default
        self._trail_duration = 30     # default 30s
        self._smooth_3d_motion = False
        self._smooth_3d_seconds = 0.5
        self._smooth_display_pose = None
        self._smooth_last_time = None
        if not embedded:
            self.setWindowTitle("JanPNP Telemetry"); self.resize(1200, 800)
            self._init_menu()
        self._init_ui(); self._start()
        if not embedded:
            self.showMaximized()
            # See app.py: X11/GNOME needs an explicit raise, Windows does not.
            self.raise_()
            self.activateWindow()

    def _init_menu(self):
        view_menu = self.menuBar().addMenu("View")
        self.smooth_motion_action = QAction("Smooth 3D Motion (0.5s)", self)
        self.smooth_motion_action.setCheckable(True)
        self.smooth_motion_action.setChecked(self._smooth_3d_motion)
        self.smooth_motion_action.toggled.connect(self.set_smooth_3d_motion)
        view_menu.addAction(self.smooth_motion_action)

    def _init_ui(self):
        cw = QWidget(); self.setCentralWidget(cw)
        lo = QVBoxLayout(cw); lo.setSpacing(4)

        # Status bar — compact
        bar = QHBoxLayout()
        self.pl = QLabel("X:  0.0  Y:  0.0  Z:  20.0")
        self.pl.setStyleSheet("font: bold 13px monospace;")
        bar.addWidget(self.pl)
        bar.addStretch()
        self.led = {}
        lo.addLayout(bar)

        # Main area: left 40% (pos+vel), right 60% (3D)
        row = QHBoxLayout(); row.setSpacing(4)
        lc = QVBoxLayout(); lc.setSpacing(4)

        # Position
        g1 = QGroupBox("Position (mm)"); v1 = QVBoxLayout(g1); v1.setContentsMargins(2,4,2,4)
        self.pp = pg.PlotWidget(); self.pp.showGrid(x=True,y=True,alpha=0.3)
        self.pp.addLegend()
        vb = self.pp.getViewBox()
        vb.setLimits(yMin=-80, yMax=350, minXRange=2, minYRange=5)
        vb.setDefaultPadding(0)
        pr = pg.mkPen(color="r",width=1.5); pg_= pg.mkPen(color="g",width=1.5); pb = pg.mkPen(color="b",width=1.5)
        self.cx = self.pp.plot([],[],pen=pr,name="X"); self.cy = self.pp.plot([],[],pen=pg_,name="Y"); self.cz = self.pp.plot([],[],pen=pb,name="Z")
        v1.addWidget(self.pp); lc.addWidget(g1)

        # Velocity
        g2 = QGroupBox("Velocity (mm/s)"); v2 = QVBoxLayout(g2); v2.setContentsMargins(2,4,2,4)
        self.vp = pg.PlotWidget(); self.vp.showGrid(x=True,y=True,alpha=0.3)
        self.vp.addLegend()
        vb2 = self.vp.getViewBox()
        vb2.setLimits(yMin=-250, yMax=250, minXRange=2, minYRange=5)
        vb2.setDefaultPadding(0)
        self.vcx = self.vp.plot([],[],pen=pr,name="X"); self.vcy = self.vp.plot([],[],pen=pg_,name="Y"); self.vcz = self.vp.plot([],[],pen=pb,name="Z")
        v2.addWidget(self.vp); lc.addWidget(g2)
        lc.setStretch(0,1); lc.setStretch(1,1)

        # 3D
        if GL_OK:
            self.gl = GLW3D()
            frame = QFrame()
            frame.setFrameStyle(QFrame.Box)
            frame.setStyleSheet("QFrame { border: 1px solid #444; }")
            fl = QVBoxLayout(frame); fl.setContentsMargins(0,0,0,0)
            fl.addWidget(self.gl)
            rw = frame
        else:
            rw = QLabel("3D unavailable (pip install pyqtgraph PyOpenGL)"); rw.setAlignment(Qt.AlignCenter)
            rw.setStyleSheet("font-size:18px;")

        row.addLayout(lc, 40); row.addWidget(rw, 60); lo.addLayout(row, 1)

        # Bottom bar
        bt = QHBoxLayout()
        b = QPushButton(f"Pi: {self.pi_url}"); b.setEnabled(False)
        self.ph = QLabel("Poll: -- Hz"); self.ph.setStyleSheet("font:12px monospace")
        bt.addWidget(b); bt.addStretch(); bt.addWidget(self.ph)
        lo.addLayout(bt)

        self.timer = QTimer(); self.timer.timeout.connect(self._tick); self.timer.start(50)
        self._pc = 0; self._pt = time.time()

    def set_trail_visible(self, visible):
        self._trail_visible = visible
        if GL_OK and GL_BACKEND == "pyqtgraph":
            self.gl.set_trail_visible(visible)

    def set_smooth_3d_motion(self, enabled):
        self._smooth_3d_motion = bool(enabled)
        self._smooth_display_pose = None
        self._smooth_last_time = None

    def _get_3d_display_pose(self, x, y, z, h, now):
        target = np.array(
            [
                float(x or 0.0),
                float(y or 0.0),
                float(z or 0.0),
                float(h or 0.0),
            ],
            dtype=float,
        )
        if not self._smooth_3d_motion:
            self._smooth_display_pose = target
            self._smooth_last_time = now
            return tuple(target)
        if self._smooth_display_pose is None or self._smooth_last_time is None:
            self._smooth_display_pose = target
            self._smooth_last_time = now
            return tuple(target)
        dt = max(0.0, float(now - self._smooth_last_time))
        self._smooth_last_time = now
        if self._smooth_3d_seconds <= 0:
            alpha = 1.0
        else:
            alpha = 1.0 - math.exp(-dt / self._smooth_3d_seconds)
        alpha = max(0.0, min(1.0, alpha))
        self._smooth_display_pose = self._smooth_display_pose + (target - self._smooth_display_pose) * alpha
        return tuple(self._smooth_display_pose)

    def set_trail_duration(self, seconds):
        self._trail_duration = seconds

    def set_cookie(self, cookie):
        if hasattr(self, 'f') and self.f:
            self.f.set_cookie(cookie)

    def clear_trail(self):
        """Clear all accumulated trail data."""
        self.tx.clear()
        self.ty.clear()
        self.tz.clear()
        if GL_OK:
            self.gl.clear_trail()

    def _start(self):
        if hasattr(self, 'f') and self.f:
            self.f.running = False
        self.f = Fetcher(f"{self.pi_url}/api/telemetry", pi_url=self.pi_url)
        self.f.start()

    def _tick(self):
        if self._busy: return
        self._busy = True
        try:
            d = self.f.get()
            if not d: return
            self._pc += 1
            if time.time() - self._pt >= 2:
                self.ph.setText(f"Poll: {self._pc/(time.time()-self._pt):.0f} Hz")
                self._pc = 0; self._pt = time.time()

            pos = d.get("position",{}); vel = d.get("velocity",{})
            ar = d.get("arrived",{}); en = d.get("enabled",{}); fl = d.get("fault",0)
            xp=pos.get("x",0); yp=pos.get("y",0); zp=pos.get("z",0); hp=pos.get("h",0)
            self.pl.setText(f"X:{xp:6.1f} Y:{yp:6.1f} Z:{zp:5.1f} H:{hp:5.1f}")
            now = time.time()
            self.t.append(now); self.px.append(xp); self.py.append(yp); self.pz.append(zp)
            self.vx.append(vel.get("x",0)); self.vy.append(vel.get("y",0)); self.vz.append(vel.get("z",0))
            self.tx.append(xp); self.ty.append(yp); self.tz.append(zp)

            tl = list(self.t)
            if len(tl) >= 2:
                t0 = tl[0]; tr = [x-t0 for x in tl]
                self.cx.setData(tr, list(self.px)); self.cy.setData(tr, list(self.py)); self.cz.setData(tr, list(self.pz))
                self.vcx.setData(tr, list(self.vx)); self.vcy.setData(tr, list(self.vy)); self.vcz.setData(tr, list(self.vz))
                # Auto-scroll X to show last 30s
                latest = tr[-1]
                self.pp.setXRange(max(0, latest - 30), latest + 2, padding=0)
                self.vp.setXRange(max(0, latest - 30), latest + 2, padding=0)

            if GL_OK:
                trail = list(zip(list(self.tx), list(self.ty), list(self.tz)))
                tool_offsets = self.f.get_tool_offsets()
                balance_z = self.f.get_balance_z()
                bottom_camera_origin = self.f.get_visit_2cam()
                feeder_origins, active_feeders = self.f.get_feeders()
                pcb_model_state, pcb_model_data, pcb_model_preview = self.f.get_pcb_model()
                runtime_tool_offsets = _tool_offsets_from_pcb_state(
                    pcb_model_state
                )
                if runtime_tool_offsets:
                    tool_offsets = runtime_tool_offsets
                display_x, display_y, display_z, display_h = (
                    self._get_3d_display_pose(xp, yp, zp, hp, now)
                )
                show_trail = self._trail_visible
                if show_trail:
                    if self._trail_duration > 0:
                        max_samples = int(self._trail_duration * 20)
                        trail = trail[-max_samples:]
                    if len(trail) < 2:
                        show_trail = False
                if GL_BACKEND == "pyqtgraph":
                    self.gl.set_tool_offsets(tool_offsets)
                    self.gl.set_bottom_camera_origin(bottom_camera_origin)
                    self.gl.set_feeders(feeder_origins, active_feeders)
                    self.gl.set_board_scan(d.get("board_scan"))
                    self.gl.set_pcb_model(
                        pcb_model_state, pcb_model_data, pcb_model_preview
                    )
                    self.gl.set_pose(display_x, display_y, display_z, trail, balance_z=balance_z, h=display_h)
                else:
                    self.gl.set_tool_offsets(tool_offsets)
                    self.gl.set_bottom_camera_origin(bottom_camera_origin)
                    self.gl.set_feeders(feeder_origins, active_feeders)
                    self.gl.set_board_scan(d.get("board_scan"))
                    self.gl.set_pcb_model(
                        pcb_model_state, pcb_model_data, pcb_model_preview
                    )
                    self.gl.set_pose(display_x, display_y, display_z, trail, show_trail=show_trail, balance_z=balance_z, h=display_h)
        finally:
            self._busy = False
