import time, threading, json
from collections import deque

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGroupBox, QGridLayout, QPushButton, QFrame, QSizePolicy)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPalette

import pyqtgraph as pg
import numpy as np


# ═══ System fetcher (background HTTP poll) ═══

class PerfFetcher(threading.Thread):
    def __init__(self, pi_url):
        super().__init__(daemon=True)
        self.url = pi_url + "/api/system"
        self._lock = threading.Lock()
        self.last_stats = {}
        self.last_ping_ms = None
        self.running = False
        self._cookie = ""

    def set_cookie(self, c):
        self._cookie = c

    def run(self):
        self.running = True
        import urllib.request as R
        while self.running:
            t0 = time.time()
            try:
                h = {"Cookie": self._cookie} if self._cookie else {}
                raw = R.urlopen(R.Request(self.url, headers=h), timeout=3).read()
                d = json.loads(raw)
                with self._lock:
                    self.last_stats = d
                    self.last_ping_ms = (time.time() - t0) * 1000
            except Exception:
                with self._lock:
                    self.last_ping_ms = None
            time.sleep(1.0)


# ═══ Metric card ═══

class MetricCard(QGroupBox):
    def __init__(self, title, unit=""):
        super().__init__(title)
        self.setAlignment(Qt.AlignCenter)
        lo = QVBoxLayout(self)
        lo.setContentsMargins(6, 8, 6, 8)
        lo.setAlignment(Qt.AlignCenter)
        self._val = QLabel("--")
        self._val.setAlignment(Qt.AlignCenter)
        self._val.setStyleSheet("font: bold 24px monospace;")
        lo.addWidget(self._val)
        self._unit = unit
        self._sub = QLabel("")
        self._sub.setAlignment(Qt.AlignCenter)
        self._sub.setStyleSheet("font: 10px;")
        lo.addWidget(self._sub)

    def set_value(self, v, sub=""):
        self._val.setText(f"{v}{self._unit}")
        if sub:
            self._sub.setText(sub)


# ═══ Graph panel ═══

class PerfGraph(QGroupBox):
    def __init__(self, title):
        super().__init__(title)
        lo = QVBoxLayout(self)
        lo.setContentsMargins(2, 4, 2, 4)
        self._plot = pg.PlotWidget()
        self._plot.showGrid(x=True, y=True, alpha=0.3)
        self._plot.setSizePolicy(self._plot.sizePolicy().horizontalPolicy(),
                                  QSizePolicy.Expanding)
        self._curve = self._plot.plot([], [], pen=pg.mkPen(color="#4af", width=1.5))
        lo.addWidget(self._plot)

    def set_data(self, xs, ys):
        if len(xs) >= 2:
            self._curve.setData(xs, ys)
            self._plot.setXRange(max(0, xs[-1] - 60), xs[-1] + 1, padding=0)


# ═══ Tab ═══

class PerformanceTab(QWidget):
    def __init__(self, pi_url="http://192.168.3.13:8080", parent=None):
        super().__init__(parent)
        self.pi_url = pi_url
        self._hist = 600

        self._t_cpu = deque(maxlen=self._hist)
        self._v_cpu = deque(maxlen=self._hist)
        self._t_mem = deque(maxlen=self._hist)
        self._v_mem = deque(maxlen=self._hist)
        self._t_ping = deque(maxlen=self._hist)
        self._v_ping = deque(maxlen=self._hist)
        self._t_temp = deque(maxlen=self._hist)
        self._v_temp = deque(maxlen=self._hist)
        self._start = time.time()

        self._init_ui()

        self._fetcher = PerfFetcher(self.pi_url)
        self._fetcher.start()

        self._tick_timer = QTimer()
        self._tick_timer.timeout.connect(self._tick)
        self._tick_timer.start(200)

    def set_cookie(self, c):
        self._fetcher.set_cookie(c)

    # ── UI ──

    def _init_ui(self):
        lo = QVBoxLayout(self)
        lo.setSpacing(8)
        lo.setContentsMargins(10, 10, 10, 10)

        # ── Header ──
        hdr = QHBoxLayout()
        self._g_elapsed = MetricCard("Uptime", " s")
        hdr.addWidget(self._g_elapsed)
        self._g_ping = MetricCard("Latency", " ms")
        hdr.addWidget(self._g_ping)
        self._g_cpu = MetricCard("CPU", "%")
        hdr.addWidget(self._g_cpu)
        self._g_mem = MetricCard("Memory", "%")
        hdr.addWidget(self._g_mem)
        self._g_temp = MetricCard("Temp", "\u00b0C")
        hdr.addWidget(self._g_temp)
        lo.addLayout(hdr)

        # ── Graphs ──
        g1 = QHBoxLayout()
        self._gr_ping = PerfGraph("Latency (ms)")
        g1.addWidget(self._gr_ping)
        self._gr_cpu = PerfGraph("CPU (%)")
        g1.addWidget(self._gr_cpu)
        lo.addLayout(g1)

        g2 = QHBoxLayout()
        self._gr_mem = PerfGraph("Memory (%)")
        g2.addWidget(self._gr_mem)
        self._gr_temp = PerfGraph("Temperature (\u00b0C)")
        g2.addWidget(self._gr_temp)
        lo.addLayout(g2)

        # ── Info bar ──
        bar = QHBoxLayout()
        self._info = QLabel(f"  {self.pi_url}")
        self._info.setStyleSheet("font: 10px monospace;")
        bar.addWidget(self._info)
        bar.addStretch()
        lo.addLayout(bar)

    # ── Tick ──

    def _tick(self):
        s = self._fetcher.last_stats or {}
        cpu = s.get("cpu", 0)
        mem = s.get("mem", 0)
        tmp = s.get("temp", 0)
        ping = self._fetcher.last_ping_ms

        elapsed = time.time() - self._start

        # Cards
        self._g_elapsed.set_value(f"{elapsed:.0f}")
        self._g_cpu.set_value(f"{cpu:.1f}")
        self._g_mem.set_value(f"{mem:.1f}")
        self._g_temp.set_value(f"{tmp:.0f}")
        if ping is not None:
            self._g_ping.set_value(f"{ping:.0f}")

        # History
        t = elapsed
        self._t_cpu.append(t); self._v_cpu.append(cpu)
        self._t_mem.append(t); self._v_mem.append(mem)
        self._t_ping.append(t); self._v_ping.append(ping or 0)
        self._t_temp.append(t); self._v_temp.append(tmp)

        self._gr_cpu.set_data(list(self._t_cpu), list(self._v_cpu))
        self._gr_mem.set_data(list(self._t_mem), list(self._v_mem))
        self._gr_ping.set_data(list(self._t_ping), list(self._v_ping))
        if tmp > 0:
            self._gr_temp.set_data(list(self._t_temp), list(self._v_temp))
