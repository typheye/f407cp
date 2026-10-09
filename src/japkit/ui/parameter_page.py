"""Live machine parameters and hardware status page."""

import time
from collections import deque

import pyqtgraph as pg
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QAbstractItemView, QGridLayout, QGroupBox, QHBoxLayout, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from depends.preview import Fetcher


class MultiPerfGraph(QGroupBox):
    """Performance-style plot with multiple live curves."""

    COLORS = ("#4af", "#ff8c42", "#7ed957", "#ff5c8a")

    def __init__(self, title, labels):
        super().__init__(title)
        self._labels = list(labels)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 4, 2, 4)
        self._plot = pg.PlotWidget()
        self._plot.showGrid(x=True, y=True, alpha=0.3)
        self._plot.addLegend(offset=(8, 8))
        self._curves = []
        for label, color in zip(self._labels, self.COLORS):
            curve = self._plot.plot([], [], pen=pg.mkPen(color=color, width=1.6), name=label)
            self._curves.append(curve)
        layout.addWidget(self._plot)

    def set_data(self, xs, series_map):
        if len(xs) < 2:
            return
        for label, curve in zip(self._labels, self._curves):
            curve.setData(xs, series_map.get(label, []))
        self._plot.setXRange(max(0, xs[-1] - 60), xs[-1] + 1, padding=0)


class ParameterPage(QWidget):
    HISTORY = 600
    SERIES = {
        "Position": ("X", "Y", "Z", "H"),
        "Speed": ("XL", "XR", "Y", "Z"),
        "Bus Voltage": ("XL", "XR", "Y", "Z"),
        "Phase Current": ("XL", "XR", "Y", "Z"),
    }
    KEY_ALIASES = {
        "X": ("x",),
        "Y": ("y",),
        "Z": ("z",),
        "H": ("h",),
        "XL": ("xl", "x"),
        "XR": ("xr", "x"),
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
            group: {label: deque(maxlen=self.HISTORY) for label in labels}
            for group, labels in self.SERIES.items()
        }
        self._graphs = {}
        self._build_ui()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(100)

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(10)

        left_box = QWidget()
        left_layout = QGridLayout(left_box)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)
        for index, (title, labels) in enumerate(self.SERIES.items()):
            graph = MultiPerfGraph(title, labels)
            self._graphs[title] = graph
            left_layout.addWidget(graph, index // 2, index % 2)

        right_box = QGroupBox("Hardware Status")
        right_layout = QVBoxLayout(right_box)
        self._status = QTableWidget(0, 2)
        self._status.setHorizontalHeaderLabels(["Item", "Value"])
        self._status.verticalHeader().setVisible(False)
        self._status.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._status.setAlternatingRowColors(True)
        self._status_rows = [
            ("Light 1 brightness", "light1"),
            ("Light 2 brightness", "light2"),
            ("Cooling fan", "fan"),
            ("Valve 1", "valve1"),
            ("Valve 2", "valve2"),
            ("Pump 1", "pump1"),
            ("Pump 2", "pump2"),
        ] + [(f"Feeder {i}", f"feeder{i}") for i in range(1, 13)]
        self._status.setRowCount(len(self._status_rows))
        for row, (label, _) in enumerate(self._status_rows):
            self._status.setItem(row, 0, QTableWidgetItem(label))
            self._status.setItem(row, 1, QTableWidgetItem("--"))
        self._status.resizeColumnsToContents()
        right_layout.addWidget(self._status)

        root.addWidget(left_box, 7)
        root.addWidget(right_box, 3)

    def start(self):
        if not self.timer.isActive():
            self.timer.start(100)
        if not self.fetcher or not self.fetcher.is_alive():
            self.fetcher = Fetcher(self.telemetry_url, pi_url=self.pi_url)
            self.fetcher.start()

    def set_cookie(self, cookie):
        self.fetcher.set_cookie(cookie)

    @staticmethod
    def _first(data, *keys, default=None):
        for key in keys:
            if key in data and data[key] is not None:
                return data[key]
        return default

    @staticmethod
    def _obj(data, *keys):
        for key in keys:
            value = data.get(key)
            if isinstance(value, dict):
                return value
        return {}

    @staticmethod
    def _to_float(value):
        try:
            if value is None or value == "--":
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    def _append_group(self, group_name, data_map):
        for label in self.SERIES[group_name]:
            aliases = self.KEY_ALIASES[label]
            value = self._to_float(self._first(data_map, *aliases))
            self._history[group_name][label].append(0.0 if value is None else value)

    def _refresh_graphs(self):
        xs = list(self._times)
        for group_name, graph in self._graphs.items():
            series_map = {
                label: list(self._history[group_name][label])
                for label in self.SERIES[group_name]
            }
            graph.set_data(xs, series_map)

    def _update_status_table(self, data):
        feeders = data.get("feeders") or data.get("fed") or []
        aliases = {
            "light1": ("light1", "l1"),
            "light2": ("light2", "l2"),
            "valve1": ("valve1", "v1"),
            "valve2": ("valve2", "v2"),
            "pump1": ("pump1", "p1"),
            "pump2": ("pump2", "p2"),
            "fan": ("fan",),
        }
        for row, (_, key) in enumerate(self._status_rows):
            if key.startswith("feeder"):
                index = int(key[6:]) - 1
                raw = feeders[index] if index < len(feeders) else None
                if raw in (2, "2", "error", "ERROR"):
                    value = "Error"
                elif raw in (1, "1", "running", "RUNNING"):
                    value = "Running"
                else:
                    value = "Idle"
            else:
                value = self._first(data, *aliases.get(key, (key,)), default="--")
                if key in {"fan", "valve1", "valve2", "pump1", "pump2"} and value != "--":
                    value = "On" if bool(value) else "Off"
            self._status.setItem(row, 1, QTableWidgetItem(str(value)))

    def _tick(self):
        if self._busy:
            return
        self._busy = True
        try:
            data = self.fetcher.get()
            if not data:
                return
            pos = self._obj(data, "position")
            vel = self._obj(data, "speed", "velocity")
            vbus = self._obj(data, "vbus", "bus_voltage", "voltage")
            curr = self._obj(data, "current", "curr", "phase_current")

            self._times.append(time.time() - self._start_time)
            self._append_group("Position", pos)
            self._append_group("Speed", vel)
            self._append_group("Bus Voltage", vbus)
            self._append_group("Phase Current", curr)
            self._refresh_graphs()
            self._update_status_table(data)
        finally:
            self._busy = False

    def stop(self):
        self.timer.stop()
        if self.fetcher:
            self.fetcher.running = False
