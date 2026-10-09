#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
******************************************************************************
* @file    app.py
* @author  JanPNP Development Team
* @brief   JAPKit unified application — dark/light theme, dynamic tabs.
******************************************************************************
* @attention
*
* Copyright (c) 2026 JanPNP Development Team. All rights reserved.
******************************************************************************
"""

import sys
import os
import subprocess

# ── PyOpenGL / Qt GL backend alignment (Linux) ────────────────────────────────
# PyOpenGL and Qt pick their GL backends independently on Linux: PyOpenGL
# defaults to EGL, while PyQt5 defaults to the X11 (xcb/GLX) platform unless
# QT_QPA_PLATFORM asks for Wayland. When the two disagree,
# EGLPlatform.GetCurrentContext() returns None, every GL call then raises
# "Attempt to retrieve context when no valid context", and the 3D page paints as
# a flat colour. This must run before anything imports OpenGL/pyqtgraph.opengl.
if sys.platform.startswith("linux") and "PYOPENGL_PLATFORM" not in os.environ:
    if os.environ.get("QT_QPA_PLATFORM", "").startswith("wayland"):
        os.environ["PYOPENGL_PLATFORM"] = "egl"
    elif os.environ.get("DISPLAY"):
        os.environ["PYOPENGL_PLATFORM"] = "glx"

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QDialog, QProxyStyle, QStyle,
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QAction, QActionGroup, QMenu, QMessageBox, QProgressBar,
    QWidget, QTabBar,
)
from PyQt5.QtCore import Qt, QSettings, QTimer
from PyQt5.QtGui import QPalette, QColor, QIcon, QPainter, QPixmap, QPen

from ui.gray_detection_page import GrayDetectionPage
from ui.home_page import Home3DPage
from ui.parameter_page import ParameterPage
from ui.performance_page import PerformancePage
from ui.sub_monitor_page import SubMonitorPage


# ── PyInstaller resource path helper ──────────────────────────

def _resource_path(relative_path: str) -> str:
    """Get absolute path to a resource file.
    Works for development (source) and PyInstaller-frozen builds.
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


# ═══════════════════ Theme ══════════════════════════════════════

THEME_SYSTEM = "system"
THEME_LIGHT  = "light"
THEME_DARK   = "dark"
def _system_is_dark() -> bool:
    """Follow the desktop colour-scheme preference (GNOME/GSettings)."""
    try:
        out = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
            capture_output=True, text=True, timeout=2)
        return "prefer-dark" in out.stdout
    except Exception:
        return False


def _dark_palette():
    p = QPalette()
    p.setColor(QPalette.Window,          QColor(30, 30, 30))
    p.setColor(QPalette.WindowText,      QColor(212, 212, 212))
    p.setColor(QPalette.Base,            QColor(26, 26, 26))
    p.setColor(QPalette.AlternateBase,   QColor(37, 37, 38))
    p.setColor(QPalette.ToolTipBase,     QColor(37, 37, 38))
    p.setColor(QPalette.ToolTipText,     QColor(212, 212, 212))
    p.setColor(QPalette.Text,            QColor(212, 212, 212))
    p.setColor(QPalette.Button,          QColor(51, 51, 51))
    p.setColor(QPalette.ButtonText,      QColor(212, 212, 212))
    p.setColor(QPalette.BrightText,      QColor(244, 71, 71))
    p.setColor(QPalette.Link,            QColor(0, 122, 204))
    p.setColor(QPalette.Highlight,       QColor(9, 71, 113))
    p.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    p.setColor(QPalette.Disabled, QPalette.Text,       QColor(100, 100, 100))
    p.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(100, 100, 100))
    return p


def _pyqtgraph_dark():
    try:
        import pyqtgraph as pg
        pg.setConfigOption('background', '#1e1e1e')
        pg.setConfigOption('foreground', '#d4d4d4')
    except Exception:
        pass


def apply_theme(app: QApplication, mode: str):
    """Apply light / dark / system theme. Callable at any time."""
    dark = (mode == THEME_DARK) or (mode == THEME_SYSTEM and _system_is_dark())
    app.setStyle("Fusion")
    if dark:
        app.setPalette(_dark_palette())
        _pyqtgraph_dark()
    else:
        app.setPalette(app.style().standardPalette())
    return dark


# ═══════════════════ IP Dialog ═════════════════════════════════

class IPDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("JAPKit")
        self.setWindowIcon(QIcon(_resource_path(
            os.path.join("japkit", "assets", "favicon.ico")
            if hasattr(sys, '_MEIPASS') else
            os.path.join("assets", "favicon.ico")
        )))
        self.setFixedSize(380, 252)
        self._edit_h = 252
        self._bar_h = 80
        # Give the dialog its own top-level frame and drop the context-help button
        self.setWindowFlags((self.windowFlags() | Qt.Window) & ~Qt.WindowContextHelpButtonHint)
        self._settings = QSettings("JanPNP", "JAPKit")

        lo = QVBoxLayout(self)
        lo.setSpacing(8)
        lo.setContentsMargins(20, 14, 20, 14)

        self._label = QLabel("")
        self._label.hide()
        lo.addWidget(self._label)

        self._lbl_user = QLabel("Username")
        lo.addWidget(self._lbl_user)
        self._user = QLineEdit()
        self._user.setPlaceholderText("Input your username")
        self._user.setText(self._settings.value("auth/user", ""))
        self._user.textChanged.connect(lambda t: self._settings.setValue("auth/user", t))
        lo.addWidget(self._user)

        self._lbl_pass = QLabel("Password")
        lo.addWidget(self._lbl_pass)
        self._pass = QLineEdit()
        self._pass.setPlaceholderText("Input your password")
        self._pass.setEchoMode(QLineEdit.Password)
        self._pass.setStyleSheet("QLineEdit { lineedit-password-character: 8901; }")
        self._pass.setText(self._settings.value("auth/pass", ""))
        self._pass.textChanged.connect(lambda t: self._settings.setValue("auth/pass", t))
        self._pass.returnPressed.connect(self._do_connect)
        lo.addWidget(self._pass)

        self._lbl_ip = QLabel("IP Address")
        lo.addWidget(self._lbl_ip)
        self._ip = QLineEdit()
        self._ip.setPlaceholderText("Input your device's ip address")
        self._ip.setText(self._settings.value("auth/ip", ""))
        self._ip.textChanged.connect(lambda t: self._settings.setValue("auth/ip", t))
        self._ip.returnPressed.connect(self._do_connect)
        lo.addWidget(self._ip)

        self._btn = QPushButton("Connect")
        self._btn.setMinimumHeight(36)
        self._btn.clicked.connect(self._do_connect)
        lo.addSpacing(8)
        lo.addWidget(self._btn)

        self._bar = QProgressBar()
        self._bar.setMaximum(10)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.hide()
        lo.addWidget(self._bar)
        lo.addStretch(1)

        self._edit_widgets = [self._user, self._pass, self._ip, self._btn,
                             self._lbl_user, self._lbl_pass, self._lbl_ip]
        self._result = None
        self._cookie = None
        self._connecting = False

    def _do_connect(self):
        if self._connecting:
            return
        self._connecting = True
        self._label.setText("Connecting...")
        self._label.show()
        for w in self._edit_widgets:
            w.hide()
        self.setFixedSize(380, self._bar_h)
        self._bar.setValue(0)
        self._bar.show()
        QApplication.processEvents()

        self._bar_tick = 0
        self._bar_timer = QTimer(self)
        self._bar_timer.timeout.connect(self._bar_step)
        self._bar_timer.start(100)

    def _bar_step(self):
        self._bar_tick += 1
        self._bar.setValue(self._bar_tick)
        if self._bar_tick >= 10:
            self._bar_timer.stop()
            self._try_connect()

    def _try_connect(self):
        ip = self._ip.text().strip()
        if not ip:
            self._reset_ui("IP Address is required")
            return
        self._result = f"http://{ip}:8080"
        user = self._user.text().strip()
        pw = self._pass.text().strip()

        # Try with auth first
        try:
            import urllib.request as R, json
            if user or pw:
                creds = json.dumps({"username": user or "janpnp",
                                    "password": pw or "admin123"}).encode()
                req = R.Request(self._result + "/api/login", data=creds,
                              headers={"Content-Type": "application/json"})
                resp = R.urlopen(req, timeout=5)
                if resp.status == 200:
                    self._cookie = resp.headers.get("Set-Cookie", "")
                resp.close()
            # Verify connection
            hdrs = {"Cookie": self._cookie} if self._cookie else {}
            req2 = R.Request(self._result + "/api/debug/status", headers=hdrs)
            R.urlopen(req2, timeout=3).close()
            super().accept()
        except Exception as e:
            self._reset_ui(str(e)[:80])

    def _reset_ui(self, err_msg):
        self._bar.hide()
        self._label.hide()
        for w in self._edit_widgets:
            w.show()
        self.setFixedSize(380, self._edit_h)
        self._connecting = False
        QMessageBox.warning(self, "JAPKit", f"Connection failed:\n{err_msg}")

    def get_cookie(self):
        return self._cookie or ""

    def get_url(self):
        return self._result or ""


class _TabBar(QTabBar):
    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), self.palette().color(QPalette.Window))
        p.end()
        super().paintEvent(e)


_TAB_FRAME_PRIMITIVES = {
    QStyle.PE_FrameTabWidget,
    getattr(QStyle, "PE_FrameTabBarBase", None),
}
_TAB_FRAME_PRIMITIVES.discard(None)


class _TabWidgetStyle(QProxyStyle):
    def drawPrimitive(self, element, option, painter, widget=None):
        if element in _TAB_FRAME_PRIMITIVES:
            return
        super().drawPrimitive(element, option, painter, widget)


_TAB_STYLE = """
QTabWidget { border: 0px; }
QTabWidget::pane { border: 0px; margin: 0px; top: 0px; }
QTabWidget::tab-bar { left: 0px; }
QTabBar { border: 0px; }
QTabBar::base { height: 0px; border: 0px; }
"""


# ═══════════════════ Main Window ════════════════════════════════

class JAPKitWindow(QMainWindow):
    def __init__(self, pi_url: str, cookie: str = ""):
        super().__init__()
        self.setWindowTitle("JAPKit")
        self.setWindowIcon(QIcon(_resource_path(
            os.path.join("japkit", "assets", "favicon.ico")
            if hasattr(sys, '_MEIPASS') else
            os.path.join("assets", "favicon.ico")
        )))
        self.setMinimumSize(800, 500)
        self.pi_url = pi_url
        self._cookie = cookie
        self._settings = QSettings("JanPNP", "JAPKit")
        self._theme_mode = self._settings.value("theme/mode", THEME_SYSTEM)

        # ── Create all content widgets once ──
        self._gray = GrayDetectionPage(embedded=True, pi_url=pi_url)
        self._gray_page = self._gray.centralWidget()
        self._gray_page.setParent(None)

        self._home3d = Home3DPage(pi_url=pi_url)
        if cookie:
            self._home3d.set_cookie(cookie)
        self._parameter = ParameterPage(pi_url=pi_url)
        self._sub_monitor = SubMonitorPage(pi_url=pi_url)

        self._perf = PerformancePage(pi_url=pi_url)
        if cookie:
            self._perf.set_cookie(cookie)

        # Home is the full-screen live 3D workspace.
        self._home = self._home3d

        # ── Menus ──
        self._build_menus()

        # ── Tab widget with custom-painted close buttons ──
        self._tabs = QTabWidget()
        self._tabs.setTabBar(_TabBar())
        self._tabs.setMovable(True)
        self._tabs.setDocumentMode(True)
        self._tabs.setTabsClosable(False)
        self._tabs.setStyleSheet(_TAB_STYLE)
        self._install_tab_style()
        self._close_icon = self._make_close_icon()
        self._tabs.tabCloseRequested.connect(self._close_tab)
        self._tabs.currentChanged.connect(self._on_tab_changed)
        self.setCentralWidget(self._tabs)

        idx = self._tabs.addTab(self._home, "Home")
        self._tabs.tabBar().setTabButton(idx, QTabBar.RightSide, None)

        self._tab_pages = {
            "BasicVin Debug": self._gray_page,
            "Parameter":     self._parameter,
            "Sub Monitor":    self._sub_monitor,
            "Performance":   self._perf,
        }

        self._restore()
        self._on_tab_changed(0)
        self._restore_session()
        self.showMaximized()
        # X11/GNOME does not raise and focus a newly mapped top-level window the
        # way Windows does. Without an explicit request the window stays behind
        # whatever had focus when the login dialog closed -- GNOME's
        # focus-new-windows='smart' then declines to focus it, so it never comes
        # to the front on its own.
        self.raise_()
        self.activateWindow()

    def _install_tab_style(self):
        base = QApplication.instance().style()
        self._tab_widget_style = _TabWidgetStyle(base)
        self._tab_bar_style = _TabWidgetStyle(base)
        self._tabs.setStyle(self._tab_widget_style)
        self._tabs.tabBar().setStyle(self._tab_bar_style)

    # ── Custom close button ───────────────────────────────────

    def _make_close_icon(self):
        pm = QPixmap(24, 24)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(160, 160, 160), 1.5))
        p.drawLine(8, 8, 16, 16)
        p.drawLine(16, 8, 8, 16)
        p.end()
        return QIcon(pm)

    def _add_close_btn(self, idx):
        btn = QPushButton()
        btn.setIcon(self._close_icon)
        btn.setFlat(True)
        btn.setFixedSize(22, 22)
        btn.setStyleSheet("QPushButton { border: none; } QPushButton:hover { background: rgba(255,0,0,0.25); border-radius: 4px; }")
        btn.clicked.connect(lambda: self._tabs.tabCloseRequested.emit(idx))
        self._tabs.tabBar().setTabButton(idx, QTabBar.RightSide, btn)

    # ── Menus ──────────────────────────────────────────────────

    def _build_menus(self):
        mb = self.menuBar()

        # File
        fm = mb.addMenu("File(&F)")
        om = fm.addMenu("Open(&O)")
        for name in ("BasicVin Debug", "Parameter", "Sub Monitor", "Performance"):
            a = QAction(name, self)
            a.setData(name)
            a.triggered.connect(self._open_tab)
            om.addAction(a)
        fm.addSeparator()

        # Theme submenu
        tm = fm.addMenu("Theme(&T)")
        self._theme_group = QActionGroup(self)
        self._theme_group.setExclusive(True)
        for label, mode in [("Follow System(&S)", THEME_SYSTEM),
                            ("Light(&L)", THEME_LIGHT),
                            ("Dark(&D)", THEME_DARK)]:
            a = QAction(label, self, checkable=True)
            a.setData(mode)
            self._theme_group.addAction(a)
            tm.addAction(a)
        self._theme_group.triggered.connect(self._on_theme)
        fm.addSeparator()

        a = QAction("Exit(&X)", self)
        a.setShortcut("Ctrl+Q")
        a.triggered.connect(self.close)
        fm.addAction(a)

        # Edit
        self._edit_menu = mb.addMenu("Edit(&E)")

        # Trajectory submenu
        self._tel_menu = QMenu("Trajectory(&T)", self)
        self._trail_on = QAction("Display trajectory(&T)", self, checkable=True)
        self._tel_menu.addAction(self._trail_on)
        self._trail_clear = QAction("Clean up trajectory(&C)", self)
        self._tel_menu.addAction(self._trail_clear)
        self._tel_menu.addSeparator()
        self._trail_time = self._tel_menu.addMenu("Track display time(&M)")
        self._trail_time.setEnabled(False)
        self._time_group = QActionGroup(self)
        self._time_group.setExclusive(True)
        for lb, sec in [("10s(&1)",10),("30s(&3)",30),("60s(&6)",60),
                        ("120s(&2)",120),("300s(&5)",300),("Persistent(&P)",0)]:
            a = QAction(lb, self, checkable=True)
            a.setData(sec)
            self._time_group.addAction(a)
            self._trail_time.addAction(a)
        self._trail_on.toggled.connect(lambda c: self._trail_time.setEnabled(c))
        self._trail_on.toggled.connect(lambda c: self._settings.setValue("telemetry/trail_visible", c))
        self._trail_on.toggled.connect(lambda c: self._home3d.set_trail_visible(c))
        self._trail_clear.triggered.connect(lambda: self._home3d.clear_trail())
        self._time_group.triggered.connect(lambda a: self._settings.setValue("telemetry/trail_duration", a.data()))
        self._time_group.triggered.connect(lambda a: self._home3d.set_trail_duration(a.data()))
        self._smooth_motion = QAction("Smooth 3D Motion (0.5s)", self, checkable=True)
        self._smooth_motion.toggled.connect(lambda c: self._settings.setValue("telemetry/smooth_3d_motion", c))
        self._smooth_motion.toggled.connect(lambda c: self._home3d.set_smooth_3d_motion(c))

        self._demo_mode = QAction("Demo Mode", self, checkable=True)
        self._demo_mode.setToolTip(
            "Automatically direct the 3D camera from live machine activity"
        )
        self._demo_mode.toggled.connect(self._on_demo_mode_toggled)

        # Home-only scene visibility controls. Axes, origin, PCB and placement
        # status lines intentionally remain outside these groups.
        self._display_menu = QMenu("Display(&D)", self)
        self._display_actions = {}
        for label, key in (
            ("Pick and Top Camera", "pick_top_camera"),
            ("Bottom Camera", "bottom_camera"),
            ("Feeders", "feeders"),
            ("Workdesk", "workdesk"),
        ):
            action = QAction(label, self, checkable=True)
            action.setChecked(True)
            action.toggled.connect(
                lambda checked, part=key: self._on_display_part_toggled(part, checked)
            )
            self._display_menu.addAction(action)
            self._display_actions[key] = action

        # Home-only PCB review actions.
        self._action_menu = QMenu("Action(&A)", self)
        self._clean_pcb_modules = QAction("Clean PCB Modules", self)
        self._clean_pcb_modules.triggered.connect(self._confirm_clean_pcb_modules)
        self._action_menu.addAction(self._clean_pcb_modules)
        self._clean_scan_result = QAction("Clean Scan Result", self)
        self._clean_scan_result.triggered.connect(self._confirm_clean_scan_result)
        self._action_menu.addAction(self._clean_scan_result)

        # Help
        hm = mb.addMenu("Help(&H)")
        a = QAction("About(&A)", self)
        a.triggered.connect(lambda: QMessageBox.about(self, "About JAPKit",
            f"<b>JAPKit</b><br><br>Vision, 3D Workspace, and Machine Parameters<br><br>Connected to: {self.pi_url}"))
        hm.addAction(a)

        # Restore theme checkmarks
        for a in self._theme_group.actions():
            if a.data() == self._theme_mode:
                a.setChecked(True)
                break

    def _on_theme(self, action):
        mode = action.data()
        self._settings.setValue("theme/mode", mode)
        self._theme_mode = mode
        app = QApplication.instance()
        apply_theme(app, mode)
        # Read from QApplication directly. Child QWidget palettes may still
        # contain the previous inherited palette during this signal handler.
        self._home3d.refresh_theme(app.palette().color(QPalette.Window))
        self._tabs.setStyleSheet(_TAB_STYLE)
        self._install_tab_style()

    def _on_display_part_toggled(self, part, visible):
        self._settings.setValue(f"display/{part}", bool(visible))
        self._home3d.set_scene_part_visible(part, visible)

    def _on_demo_mode_toggled(self, enabled):
        self._settings.setValue("display/demo_mode", bool(enabled))
        self._display_menu.setEnabled(not enabled)
        self._home3d.set_demo_mode(enabled)

    def _confirm_clean_pcb_modules(self):
        answer = QMessageBox.question(
            self,
            "JAPKit",
            "Are you sure you want to clean the PCB models and review data?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            import urllib.request as request

            url = f"{self.pi_url.rstrip('/')}/api/pcb-model/clear"
            req = request.Request(
                url,
                data=b"{}",
                headers={
                    "Content-Type": "application/json",
                    "Cookie": self._cookie or "",
                },
                method="POST",
            )
            with request.urlopen(req, timeout=5) as response:
                if response.status != 200:
                    raise RuntimeError(f"Host returned HTTP {response.status}")
            self._home3d.clear_pcb_modules()
        except Exception as exc:
            QMessageBox.warning(
                self,
                "JAPKit",
                f"Failed to clean PCB models:\n{exc}",
            )

    def _confirm_clean_scan_result(self):
        answer = QMessageBox.question(
            self,
            "JAPKit",
            "Are you sure you want to clean the retained scan result?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            import urllib.request as request

            url = f"{self.pi_url.rstrip('/')}/api/board-scan/clear"
            req = request.Request(
                url,
                data=b"{}",
                headers={
                    "Content-Type": "application/json",
                    "Cookie": self._cookie or "",
                },
                method="POST",
            )
            with request.urlopen(req, timeout=5) as response:
                if response.status != 200:
                    raise RuntimeError(f"Host returned HTTP {response.status}")
            self._home3d.clear_scan_result()
        except Exception as exc:
            QMessageBox.warning(
                self,
                "JAPKit",
                f"Failed to clean scan result:\n{exc}",
            )

    def _save_session(self):
        names = []
        for i in range(self._tabs.count()):
            n = self._tabs.tabText(i)
            if n != "Home":
                names.append(n)
        self._settings.setValue("session/tabs", names)

    def _restore_session(self):
        names = self._settings.value("session/tabs", [])
        if isinstance(names, str):
            names = [names]
        for n in names:
            if n == "Gray Detection":
                n = "BasicVin Debug"
            if n in self._tab_pages:
                self._tabs.addTab(self._tab_pages[n], n)
                self._add_close_btn(self._tabs.count() - 1)
                if n == "Parameter":
                    self._parameter.start()
                    if self._cookie:
                        self._parameter.set_cookie(self._cookie)
                if n == "Sub Monitor":
                    self._sub_monitor.start()
                    if self._cookie:
                        self._sub_monitor.set_cookie(self._cookie)
                if n == "Performance" and self._cookie:
                    self._perf.set_cookie(self._cookie)

    # ── Tab management ─────────────────────────────────────────

    def _open_tab(self):
        name = self.sender().data()
        for i in range(self._tabs.count()):
            if self._tabs.tabText(i) == name:
                self._tabs.setCurrentIndex(i)
                if name == "Parameter":
                    self._parameter.start()
                    if self._cookie:
                        self._parameter.set_cookie(self._cookie)
                if name == "Sub Monitor":
                    self._sub_monitor.start()
                    if self._cookie:
                        self._sub_monitor.set_cookie(self._cookie)
                if name == "Performance" and self._cookie:
                    self._perf.set_cookie(self._cookie)
                return
        page = self._tab_pages[name]
        idx = self._tabs.addTab(page, name)
        self._add_close_btn(idx)
        self._tabs.setCurrentIndex(idx)
        if name == "Parameter":
            self._parameter.start()
            if self._cookie:
                self._parameter.set_cookie(self._cookie)
        if name == "Sub Monitor":
            self._sub_monitor.start()
            if self._cookie:
                self._sub_monitor.set_cookie(self._cookie)
        if name == "Performance" and self._cookie:
            self._perf.set_cookie(self._cookie)

    def _close_tab(self, index):
        name = self._tabs.tabText(index)
        if name == "Home":
            return
        if name == "Parameter":
            self._parameter.stop()
        if name == "Sub Monitor":
            self._sub_monitor.stop()
        self._tabs.removeTab(index)

    def _on_tab_changed(self, index):
        self._edit_menu.clear()
        if index < 0:
            return
        name = self._tabs.tabText(index)
        if name in ("BasicVin Debug", "Parameter", "Sub Monitor", "Performance"):
            self._edit_menu.menuAction().setVisible(False)
        else:
            self._edit_menu.menuAction().setVisible(True)
            if name == "Home":
                self._edit_menu.addAction(self._demo_mode)
                self._edit_menu.addSeparator()
                self._edit_menu.addMenu(self._display_menu)
                self._edit_menu.addMenu(self._action_menu)
                self._edit_menu.addMenu(self._tel_menu)
                self._edit_menu.addAction(self._smooth_motion)

    # ── Persistence ────────────────────────────────────────────

    def _restore(self):
        s = self._settings
        ton = s.value("telemetry/trail_visible", False, type=bool)
        self._trail_on.setChecked(ton)
        self._trail_time.setEnabled(ton)
        ts = s.value("telemetry/trail_duration", 30, type=int)
        for a in self._time_group.actions():
            if a.data() == ts:
                a.setChecked(True); break
        self._home3d.set_trail_visible(ton)
        self._home3d.set_trail_duration(ts)
        smooth = s.value("telemetry/smooth_3d_motion", False, type=bool)
        self._smooth_motion.setChecked(smooth)
        self._home3d.set_smooth_3d_motion(smooth)
        for part, action in self._display_actions.items():
            visible = s.value(f"display/{part}", True, type=bool)
            action.setChecked(visible)
            self._home3d.set_scene_part_visible(part, visible)
        demo_mode = s.value("display/demo_mode", False, type=bool)
        self._demo_mode.setChecked(demo_mode)
        self._display_menu.setEnabled(not demo_mode)
        self._home3d.set_demo_mode(demo_mode)

    # ── Exit ───────────────────────────────────────────────────

    def closeEvent(self, event):
        if QMessageBox.question(self, "JAPKit", "Are you sure you want to exit?",
                                QMessageBox.Yes | QMessageBox.No,
                                QMessageBox.No) == QMessageBox.Yes:
            if self._home3d:
                self._home3d.stop()
            if self._parameter:
                self._parameter.stop()
            if self._sub_monitor:
                self._sub_monitor.stop()
            self._save_session()
            event.accept()
        else:
            event.ignore()


# ═══════════════════ Entry ══════════════════════════════════════

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("JAPKit")
    app.setOrganizationName("JanPNP")

    # Window icon — handles both source and PyInstaller-frozen paths
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller bundles icon to japkit/assets/favicon.ico
        icon_path = _resource_path(os.path.join("japkit", "assets", "favicon.ico"))
    else:
        # Development: src/japkit/app.py  →  src/japkit/assets/favicon.ico
        icon_path = _resource_path(os.path.join("assets", "favicon.ico"))
    app.setWindowIcon(QIcon(icon_path))

    # Apply saved or system theme BEFORE showing any window
    s = QSettings("JanPNP", "JAPKit")
    theme_mode = s.value("theme/mode", THEME_SYSTEM)
    dark = apply_theme(app, theme_mode)

    dlg = IPDialog()
    if dlg.exec_() != QDialog.Accepted:
        return 0

    win = JAPKitWindow(dlg.get_url(), dlg.get_cookie())
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
