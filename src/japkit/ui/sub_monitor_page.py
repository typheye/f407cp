"""Live ESP32-S3 sub-board sensor monitor."""

import time
from collections import deque

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import pyqtgraph as pg

from depends.preview import Fetcher


class SensorGraph(QGroupBox):
    COLORS = ("#4af", "#ff8c42", "#7ed957")

    def __init__(self, title, labels):
        super().__init__(title)
        self.labels = tuple(labels)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 4, 2, 2)
        self.plot = pg.PlotWidget()
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        self.plot.addLegend(offset=(8, 8))
        self.curves = [
            self.plot.plot([], [], pen=pg.mkPen(color=color, width=1.6), name=label)
            for label, color in zip(self.labels, self.COLORS)
        ]
        layout.addWidget(self.plot)

    def set_data(self, xs, values):
        if len(xs) < 2:
            return
        for label, curve in zip(self.labels, self.curves):
            curve.setData(xs, values.get(label, []))
        self.plot.setXRange(max(0.0, xs[-1] - 60.0), xs[-1] + 1.0, padding=0)


class SubMonitorPage(QWidget):
    """Display real-time temperatures and nine-axis sub-board telemetry."""

    HISTORY = 600
    GROUPS = {
        "Acceleration (m/s²)": ("X", "Y", "Z"),
        "Angular Velocity (°/s)": ("X", "Y", "Z"),
        "Magnetic Field (raw)": ("X", "Y", "Z"),
        "Orientation (°)": ("Roll", "Pitch", "Yaw"),
    }

    def __init__(self, pi_url, parent=None):
        super().__init__(parent)
        self.pi_url = pi_url
        self.telemetry_url = f"{pi_url}/api/telemetry"
        self.fetcher = Fetcher(self.telemetry_url, pi_url=pi_url)
        self.fetcher.start()
        self._busy = False
        self._start_time = time.time()
        self._times = deque(maxlen=self.HISTORY)
        self._history = {
            name: {label: deque(maxlen=self.HISTORY) for label in labels}
            for name, labels in self.GROUPS.items()
        }
        self._graphs = {}
        self._build_ui()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(100)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        header = QHBoxLayout()
        self._connection = QLabel("Sub-board: --")
        self._connection.setStyleSheet("font: bold 13px monospace;")
        self._age = QLabel("Last sample: --")
        self._age.setStyleSheet("font: 13px monospace;")
        header.addWidget(self._connection)
        header.addStretch()
        header.addWidget(self._age)
        root.addLayout(header)

        content = QHBoxLayout()
        graphs = QWidget()
        graph_layout = QGridLayout(graphs)
        graph_layout.setContentsMargins(0, 0, 0, 0)
        graph_layout.setSpacing(8)
        for index, (title, labels) in enumerate(self.GROUPS.items()):
            graph = SensorGraph(title, labels)
            self._graphs[title] = graph
            graph_layout.addWidget(graph, index // 2, index % 2)
        content.addWidget(graphs, 7)

        status = QGroupBox("Sub-board Status")
        status_layout = QVBoxLayout(status)
        self._status = QTableWidget(0, 2)
        self._status.setHorizontalHeaderLabels(["Item", "Value"])
        self._status.verticalHeader().setVisible(False)
        self._status.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._status.setAlternatingRowColors(True)
        self._status_rows = [
            ("Left head temperature", "left"),
            ("Right head temperature", "right"),
            ("IMU temperature", "imu"),
            ("IMU ready", "imu_ready"),
            ("Serial port", "port"),
            ("Received lines", "received_lines"),
            ("Invalid lines", "invalid_lines"),
            ("Last error", "last_error"),
        ]
        self._status.setRowCount(len(self._status_rows))
        for row, (label, _) in enumerate(self._status_rows):
            self._status.setItem(row, 0, QTableWidgetItem(label))
            self._status.setItem(row, 1, QTableWidgetItem("--"))
        self._status.resizeColumnsToContents()
        status_layout.addWidget(self._status)
        content.addWidget(status, 3)
        root.addLayout(content, 1)

    def start(self):
        if not self.timer.isActive():
            self.timer.start(100)
        if not self.fetcher or not self.fetcher.is_alive():
            self.fetcher = Fetcher(self.telemetry_url, pi_url=self.pi_url)
            self.fetcher.start()

    def set_cookie(self, cookie):
        if self.fetcher:
            self.fetcher.set_cookie(cookie)

    @staticmethod
    def _vector(data, key):
        value = data.get(key)
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _number(value, default=0.0):
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def _append_group(self, group, source, labels):
        for label, axis in zip(labels, ("x", "y", "z")):
            value = self._number(source.get(axis))
            self._history[group][label].append(value)

    def _refresh_graphs(self):
        xs = list(self._times)
        for name, graph in self._graphs.items():
            values = {label: list(self._history[name][label]) for label in self.GROUPS[name]}
            graph.set_data(xs, values)

    def _set_status(self, sub_board):
        connected = bool(sub_board.get("connected"))
        port = sub_board.get("port") or "--"
        self._connection.setText(
            f"Sub-board: {'Connected' if connected else 'Offline'}"
            + (f" ({port})" if connected else "")
        )
        age = sub_board.get("age_seconds")
        self._age.setText(
            f"Last sample: {float(age):.1f}s ago" if age is not None else "Last sample: --"
        )

        temperatures = sub_board.get("temperature_c") or {}
        values = {
            "left": temperatures.get("left"),
            "right": temperatures.get("right"),
            "imu": temperatures.get("imu"),
            "imu_ready": "Yes" if sub_board.get("imu_ready") else "No",
            "port": port,
            "received_lines": sub_board.get("received_lines", 0),
            "invalid_lines": sub_board.get("invalid_lines", 0),
            "last_error": sub_board.get("last_error") or "--",
        }
        for row, (_, key) in enumerate(self._status_rows):
            value = values.get(key)
            if key in {"left", "right", "imu"}:
                value = "--" if value is None else f"{float(value):.1f} °C"
            self._status.setItem(row, 1, QTableWidgetItem(str(value)))

    def _tick(self):
        if self._busy:
            return
        self._busy = True
        try:
            data = self.fetcher.get() if self.fetcher else {}
            sub_board = data.get("sub_board") if data else None
            if not isinstance(sub_board, dict):
                return
            self._set_status(sub_board)
            now = time.time()
            self._times.append(now - self._start_time)
            self._append_group(
                "Acceleration (m/s²)",
                self._vector(sub_board, "acceleration_mps2"),
                self.GROUPS["Acceleration (m/s²)"],
            )
            self._append_group(
                "Angular Velocity (°/s)",
                self._vector(sub_board, "angular_velocity_dps"),
                self.GROUPS["Angular Velocity (°/s)"],
            )
            self._append_group(
                "Magnetic Field (raw)",
                self._vector(sub_board, "magnetic_raw"),
                self.GROUPS["Magnetic Field (raw)"],
            )
            self._append_group(
                "Orientation (°)",
                self._vector(sub_board, "orientation_deg"),
                self.GROUPS["Orientation (°)"],
            )
            self._refresh_graphs()
        finally:
            self._busy = False

    def stop(self):
        self.timer.stop()
        if self.fetcher:
            self.fetcher.running = False

