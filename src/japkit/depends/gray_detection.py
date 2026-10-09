#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
******************************************************************************
* @file    gray_detection.py
* @author  JanPNP Development Team
* @brief   Host-compatible BasicVin detector debug window.
******************************************************************************
* @attention
*
* Copyright (c) 2026 JanPNP Development Team. All rights reserved.
*
* This software is licensed under terms that can be found in the LICENSE file
* in the root directory of this software component.
* If no LICENSE file comes with this software, it is provided AS-IS.
*
******************************************************************************
"""
import sys
import os
import json
import cv2
import numpy as np
# Modified (added QApplication):
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFileDialog, QMessageBox, QGridLayout, QPushButton, QDialog,
    QComboBox, QGroupBox,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QImage
import urllib.request
from urllib.parse import urlparse
import threading
import time
from queue import Queue

from depends.config import (
    IMAGE_WIDTH,
    IMAGE_HEIGHT,
)
from depends.roi_tools import ROISelector
from depends.gray_image_processor import ImageProcessor
from depends.gray_ui_components import FileControlGroup, HSVControlGroup, ROIControlGroup
from depends.feeder_structured import draw_feeder_debug
from depends.basicvin_hsv_detector import HSVTargetDetector
from depends.component_check import _component_check_detector


# These are snapshots of the Host BasicVin configurations. Keeping them here
# makes BasicVin Debug deterministic when the Raspberry Pi is unavailable.
BASICVIN_DEBUG_CONFIGS = {
    "PCB Board Local": {
        "target": "board",
        "roi": {"x": 164, "y": 106, "width": 290, "height": 259},
        "hsv_thresholds": {"S_min": 0, "S_max": 167, "V_min": 0, "V_max": 255, "invert": True},
        "board_roi_guard_max_px": 36,
        "board_roi_guard_corner_count": 3,
        "board_allow_roi_edge_corner": False,
        "board_body_close_kernel_max": 81,
        "board_body_close_iterations": 1,
        "board_body_kernel_shape": "ellipse",
        "board_min_body_long_ratio": 0.45,
        "board_min_body_short_ratio": 0.18,
        "board_min_fill_ratio": 0.35,
        "board_corner_mode": "lt",
        "board_enable_circle_guard": True,
        "board_circle_dp": 1.2,
        "board_circle_min_dist_ratio": 0.1,
        "board_circle_param1": 90,
        "board_circle_param2": 18,
        "board_circle_min_radius_ratio": 0.04,
        "board_circle_max_radius_ratio": 0.18,
        "board_circle_expand_px": 8,
        "board_circle_reject_corner_band_px": 10,
        "board_circle_edge_margin_px": 12,
        "board_min_roi_coverage": 0.6,
        "board_max_roi_coverage": 80.0,
        "board_min_bbox_coverage": 35.0,
        "board_roi_guard_margin_px": 18,
        "board_roi_guard_ratio": 0.06,
        "board_enable_body_heal": False,
        "board_body_close_kernel": 41,
        "board_body_close_ratio": 0.14,
        "board_use_convex_outer_hull": True,
        "board_reject_inner_features": True,
        "board_detector_version": "component_ltop_fixed_right_down_v3_hsv_fallback",
        "board_run_guard_max_px": 18,
        "board_close_kernel": 5,
        "board_close_iterations": 1,
        "board_edge_close_kernel": 5,
        "board_edge_row_min_ratio": 0.28,
        "board_edge_col_min_ratio": 0.28,
        "board_edge_row_min_px": 35,
        "board_edge_col_min_px": 35,
        "board_edge_fit_band_px": 5,
        "board_min_area_ratio": 0.006,
        "board_min_area": 220,
        "board_full_roi_reject_coverage": 85.0,
        "board_enable_circle_fill": True,
        "board_circle_fill_expand_px": 5,
        "board_allow_circle_near_corner": True,
        "board_force_left_top_right_down": True,
        "board_expected_corner": "lt",
        "board_expected_rays": ["right", "down"],
        "board_min_right_ray_len_px": 45,
        "board_min_down_ray_len_px": 45,
        "board_min_right_ray_len_ratio": 0.16,
        "board_min_down_ray_len_ratio": 0.16,
        "board_ray_start_tolerance_px": 14,
        "board_ray_check_band_px": 6,
        "board_min_ray_coverage": 0.28,
        "board_allow_no_invert": False,
        "board_allow_white_fallback": False,
        "board_allow_component_fallback": True,
        "board_allow_mask_bbox_fallback": True,
    },
    "Feeder Chip Local": {
        "target": "feeder",
        "roi": {"x": 253, "y": 114, "width": 86, "height": 234},
        "hsv_thresholds": {"S_min": 0, "S_max": 255, "V_min": 86, "V_max": 255, "invert": True},
    },
    "Bottom Camera Recheck Pick": {
        "target": "check",
        "algorithm": "reference_difference",
        "reference_samples": 5,
        "roi_width": 360,
        "roi_height": 300,
        "min_diff_threshold": 16,
        "min_component_area_px": 70,
        "max_component_area_px": 6000,
        "max_center_distance_px": 55,
        "max_component_span_px": 90,
        "center_contact_margin_px": 8,
        "bright_component_threshold": 55,
        "bright_min_component_area_px": 100,
        "bright_max_component_area_px": 3000,
        "bright_max_component_span_px": 60,
        "exposure_roi_width": 180,
        "exposure_roi_height": 150,
        "max_white_ratio": 0.12,
        "max_luma_saturated_ratio": 0.35,
        "max_exposure_median": 235.0,
    },
    "HSV Debug": {
        "target": "hsv_debug",
        "roi": "full_image",
        "hsv_thresholds": {
            "S_min": 0,
            "S_max": 30,
            "V_min": 0,
            "V_max": 255,
            "invert": False,
        },
    },
}

HOST_BASICVIN_RESULTS_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "..",
        "host-board", "japends", "basicvin", "results",
    )
)

BASICVIN_RESULT_FILES = {
    "PCB Board Local": "board_result.json",
    "Feeder Chip Local": "feeders_result.json",
    "Bottom Camera Recheck Pick": "check_result.json",
}


class MJPEGClient:
    """MJPEG stream client with thread-safe connection management"""

    def __init__(self, url):
        self.url = url
        self.frame_queue = Queue(maxsize=2)
        self.running = False
        self.thread = None
        self.last_frame = None
        self.connected = False
        self._lock = threading.Lock()
        self._connect_event = threading.Event()
        self._first_frame_received = False
        self._last_frame_time = 0.0
        self._stale_timeout = 5.0

    def connect(self, timeout=15):
        """Start MJPEG stream capture, blocks until connected or timeout."""
        if self.running:
            return self.is_connected()

        self._connect_event.clear()
        self._first_frame_received = False
        self.running = True
        self.thread = threading.Thread(target=self._capture_stream, daemon=True)
        self.thread.start()

        # Wait for the first decoded frame, not just an accepted HTTP socket.
        ok = self._connect_event.wait(timeout=timeout)
        if ok:
            print(f"[MJPEG] Connected to {self.url}")
        else:
            print(f"[MJPEG] Connection to {self.url} timed out after {timeout}s")
        return ok

    def _capture_stream(self):
        """Capture MJPEG stream"""
        stream = None
        bytes_data = b""
        retry_delay = 1

        while self.running:
            try:
                if stream is None:
                    try:
                        req = urllib.request.Request(self.url)
                        req.add_header("User-Agent", "Mozilla/5.0")
                        req.add_header("Accept", "multipart/x-mixed-replace")
                        stream = urllib.request.urlopen(req, timeout=20)
                        bytes_data = b""
                        retry_delay = 1
                        print(f"[MJPEG] Stream connected successfully")
                    except Exception as e:
                        print(f"[MJPEG] Connection attempt failed: {e}")
                        time.sleep(retry_delay)
                        retry_delay = min(retry_delay * 2, 30)
                        continue

                # Read stream data
                chunk = stream.read(4096)
                if not chunk:
                    stream.close()
                    stream = None
                    with self._lock:
                        self.connected = False
                    time.sleep(1)
                    continue

                bytes_data += chunk

                # Find JPEG markers
                a = bytes_data.find(b"\xff\xd8")
                b = bytes_data.find(b"\xff\xd9")

                if a != -1 and b != -1 and b > a:
                    jpeg = bytes_data[a : b + 2]
                    bytes_data = bytes_data[b + 2 :]

                    frame = cv2.imdecode(
                        np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR
                    )

                    if frame is not None:
                        frame = cv2.resize(frame, (IMAGE_WIDTH, IMAGE_HEIGHT))
                        now = time.time()
                        with self._lock:
                            self.last_frame = frame
                            self.connected = True
                            self._last_frame_time = now
                        if not self._first_frame_received:
                            self._first_frame_received = True
                            self._connect_event.set()

                        if self.frame_queue.full():
                            try:
                                self.frame_queue.get_nowait()
                            except:
                                pass
                        self.frame_queue.put(frame)

                if len(bytes_data) > 1024 * 1024:
                    bytes_data = bytes_data[-65536:]

                with self._lock:
                    last_frame_time = self._last_frame_time
                    is_connected = self.connected
                if (
                    is_connected
                    and last_frame_time > 0
                    and (time.time() - last_frame_time) > self._stale_timeout
                ):
                    print(
                        f"[MJPEG] Stream stalled for {self._stale_timeout:.1f}s, reconnecting"
                    )
                    try:
                        stream.close()
                    except:
                        pass
                    stream = None
                    bytes_data = b""
                    with self._lock:
                        self.connected = False
                    time.sleep(1)

            except Exception as e:
                print(f"[MJPEG] Stream error: {e}")
                if stream:
                    try:
                        stream.close()
                    except:
                        pass
                stream = None
                with self._lock:
                    self.connected = False
                if not self._first_frame_received:
                    self._connect_event.clear()
                time.sleep(2)

    def get_frame(self):
        """Get latest frame"""
        if not self.running:
            return None

        try:
            frame = self.frame_queue.get_nowait()
            return frame
        except:
            with self._lock:
                return self.last_frame

    def is_connected(self):
        with self._lock:
            return self.connected

    def disconnect(self):
        """Stop stream"""
        self.running = False
        self._connect_event.set()
        if self.thread:
            self.thread.join(timeout=2)
        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
            except:
                break
        with self._lock:
            self.connected = False
            self.last_frame = None
            self._last_frame_time = 0.0
        self._first_frame_received = False


class MJPEGConfigDialog(QDialog):
    """Dialog for MJPEG camera selection — IP/port come from the main pi_url."""

    def __init__(self, parent=None, pi_url="http://192.168.3.13:8080"):
        super().__init__(parent)
        self.setWindowTitle("Select Camera")
        self.setModal(True)
        self.resize(320, 130)
        self.pi_url = pi_url

        try:
            self._host = urlparse(pi_url).hostname or "192.168.3.13"
        except Exception:
            self._host = "192.168.3.13"

        layout = QVBoxLayout()

        layout.addWidget(QLabel("Camera:"))
        self.cam_combo = QComboBox()
        self.cam_combo.addItems(["Camera 1 (Port 10301)", "Camera 2 (Port 10302)"])
        self.cam_combo.currentIndexChanged.connect(self._update_url)
        layout.addWidget(self.cam_combo)

        self.url_label = QLabel()
        layout.addWidget(self.url_label)

        btn_layout = QHBoxLayout()
        connect_btn = QPushButton("Connect")
        connect_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(connect_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)
        self._update_url()

    def _update_url(self):
        port = 10301 if self.cam_combo.currentIndex() == 0 else 10302
        url = f"http://{self._host}:{port}/stream"
        self.url_label.setText(f"URL: {url}")

    def get_url(self):
        port = 10301 if self.cam_combo.currentIndex() == 0 else 10302
        return f"http://{self._host}:{port}/stream"


class GrayDetector(QMainWindow):
    def __init__(self, embedded=False, pi_url="http://192.168.3.13:8080"):
        super().__init__()
        self.pi_url = pi_url
        if not embedded:
            self.setWindowTitle("BasicVin Debug")

        # Initialize components
        self.image_processor = ImageProcessor()
        self.roi_selector = ROISelector()
        self.roi_enabled = False

        # Video source
        self.current_source = "file"
        self.mjpeg_client = None
        self.update_timer = None

        self.current_item = "PCB Board Local"
        self._detectors = {
            name: HSVTargetDetector(
                dict(config),
                target_name=config["target"],
                camera_id=2 if config["target"] == "check" else 1,
            )
            for name, config in BASICVIN_DEBUG_CONFIGS.items()
            if name != "HSV Debug"
        }
        _component_check_detector.reset(2, "DEBUG")
        _component_check_detector.select_profile(2, "DEBUG")
        self._last_feeder_result = None
        self._last_feeder_result_time = 0.0
        self._last_debug_images = {}
        self._last_debug_result = {}
        self._loading_hsv_params = False

        self.init_ui()

        if not embedded:
            self.showMaximized()
            # See app.py: X11/GNOME needs an explicit raise, Windows does not.
            self.raise_()
            self.activateWindow()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # Left control panel
        control_panel = QWidget()
        control_panel.setFixedWidth(380)
        control_layout = QVBoxLayout(control_panel)
        control_layout.setSpacing(8)

        # Source selection group
        source_group = QGroupBox("Image Source")
        source_layout = QVBoxLayout()
        self.file_source_btn = QPushButton("From File")
        self.file_source_btn.clicked.connect(self.load_image)
        self.mjpeg_source_btn = QPushButton("From MJPEG Stream")
        self.mjpeg_source_btn.clicked.connect(self.switch_to_mjpeg_source)
        source_layout.addWidget(self.file_source_btn)
        source_layout.addWidget(self.mjpeg_source_btn)
        source_group.setLayout(source_layout)
        control_layout.addWidget(source_group)

        self.file_controls = FileControlGroup()
        self.file_controls.load_btn.clicked.connect(self.load_host_result)
        self.file_controls.save_btn.clicked.connect(self.save_debug_results)
        control_layout.addWidget(self.file_controls)

        # Host-compatible detector selection. This deliberately sits directly
        # below Image Source so the active detection item is always visible.
        item_group = QGroupBox("Detection Item")
        item_layout = QVBoxLayout()
        self.algo_combo = QComboBox()
        self.algo_combo.addItems(list(BASICVIN_DEBUG_CONFIGS))
        self.algo_combo.currentTextChanged.connect(self.on_algorithm_changed)
        item_layout.addWidget(QLabel("Select Item:"))
        item_layout.addWidget(self.algo_combo)
        self.reset_reference_btn = QPushButton("Reset Empty Reference")
        self.reset_reference_btn.clicked.connect(self.reset_bottom_reference)
        self.reset_reference_btn.setVisible(False)
        item_layout.addWidget(self.reset_reference_btn)
        item_group.setLayout(item_layout)
        control_layout.addWidget(item_group)

        # ROI controls
        self.roi_controls = ROIControlGroup()
        self.roi_controls.roi_btn.clicked.connect(self.toggle_roi_selection)
        self.roi_controls.clear_btn.clicked.connect(self.clear_roi)
        self.roi_controls.full_btn.clicked.connect(self.use_full_image)
        control_layout.addWidget(self.roi_controls)

        self.hsv_controls = HSVControlGroup(self)
        control_layout.addWidget(self.hsv_controls)

        control_layout.addStretch()

        # Right display area
        display_panel = QWidget()
        display_layout = QVBoxLayout(display_panel)
        display_layout.setContentsMargins(5, 5, 5, 5)

        # Info label - smaller height
        self.info_label = QLabel("PCB Board Local")
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setStyleSheet(
            "QLabel { padding: 3px; font-size: 11px; }"
        )
        self.info_label.setWordWrap(True)
        self.info_label.setMaximumHeight(40)
        display_layout.addWidget(self.info_label)

        # 2x2 grid for images - larger display
        grid_widget = QWidget()
        grid_layout = QGridLayout(grid_widget)
        grid_layout.setSpacing(8)

        # Calculate larger display size (use more screen space)
        available_width = QApplication.primaryScreen().availableGeometry().width() - 420
        available_height = (
            QApplication.primaryScreen().availableGeometry().height() - 100
        )
        new_display_width = min(500, available_width // 2)
        new_display_height = min(400, available_height // 2)

        self.image_labels = {}
        titles = [
            "Original Image",
            "Detection Mask",
            "ROI Region (Masked)",
            "Detection Overlay",
        ]
        positions = [(0, 0), (0, 1), (1, 0), (1, 1)]

        for title, pos in zip(titles, positions):
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(3, 3, 3, 3)

            title_label = QLabel(title)
            title_label.setAlignment(Qt.AlignCenter)
            title_label.setStyleSheet(
                "QLabel { font-weight: bold; padding: 2px; border-radius: 3px; font-size: 12px; }"
            )

            image_label = QLabel()
            image_label.setAlignment(Qt.AlignCenter)
            image_label.setMinimumSize(new_display_width, new_display_height)
            image_label.setStyleSheet(
                "QLabel { border: 2px solid gray; background-color: black; border-radius: 5px; }"
            )
            image_label.mousePressEvent = self.get_roi_mouse_press
            image_label.mouseMoveEvent = self.get_roi_mouse_move
            image_label.mouseReleaseEvent = self.get_roi_mouse_release

            container_layout.addWidget(title_label)
            container_layout.addWidget(image_label)
            grid_layout.addWidget(container, pos[0], pos[1])
            self.image_labels[title] = image_label

        display_layout.addWidget(grid_widget)
        main_layout.addWidget(control_panel)
        main_layout.addWidget(display_panel, stretch=1)

        # Setup timer for MJPEG stream
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_from_mjpeg)
        self._sync_hsv_controls()

    def on_algorithm_changed(self):
        """Select one Host-compatible BasicVin detection item."""
        self.current_item = self.algo_combo.currentText()
        is_bottom = self.current_item == "Bottom Camera Recheck Pick"
        self.reset_reference_btn.setVisible(is_bottom)
        self._sync_hsv_controls()
        self.info_label.setText(self.current_item)
        self.detect_gray()

    def _sync_hsv_controls(self):
        config = BASICVIN_DEBUG_CONFIGS.get(self.current_item, {})
        params = dict(config.get("hsv_thresholds", {}) or {})
        self._loading_hsv_params = True
        try:
            self.hsv_controls.set_params(params)
        finally:
            self._loading_hsv_params = False

    def reset_bottom_reference(self):
        _component_check_detector.reset(2, "DEBUG")
        _component_check_detector.select_profile(2, "DEBUG")
        self.info_label.setText("Bottom reference reset; show the empty nozzle view")

    def switch_to_file_source(self):
        """Switch to file-based image source"""
        self.stop_mjpeg_stream()
        self.current_source = "file"
        self.info_label.setText("File mode - Click 'Load Image'")

    def switch_to_mjpeg_source(self):
        """Switch to MJPEG stream source"""
        dialog = MJPEGConfigDialog(self, pi_url=self.pi_url)
        if dialog.exec_() == QDialog.Accepted:
            url = dialog.get_url()
            if url:
                self.stop_mjpeg_stream()
                self.mjpeg_client = MJPEGClient(url)
                self.info_label.setText(f"Connecting to MJPEG stream: {url} (15s timeout)...")
                QApplication.processEvents()
                ok = self.mjpeg_client.connect(timeout=15)
                if ok:
                    self.current_source = "mjpeg"
                    self.update_timer.start(33)
                    self.info_label.setText(f"MJPEG stream connected: {url}")
                else:
                    self.mjpeg_client.disconnect()
                    self.mjpeg_client = None
                    self.info_label.setText(f"MJPEG connection failed: {url}")
                    QMessageBox.warning(self, "Connection Error",
                        f"Cannot connect to MJPEG stream:\n{url}\n\n"
                        f"Please check:\n"
                        f"• The camera service is running on the target\n"
                        f"• The IP address and port are correct\n"
                        f"• Network connectivity")
                self.image_processor.set_image(None)

    def stop_mjpeg_stream(self):
        """Stop MJPEG stream"""
        if self.update_timer.isActive():
            self.update_timer.stop()
        if self.mjpeg_client:
            self.mjpeg_client.disconnect()
            self.mjpeg_client = None

    def update_from_mjpeg(self):
        """Update frame from MJPEG stream"""
        if self.current_source == "mjpeg" and self.mjpeg_client:
            frame = self.mjpeg_client.get_frame()
            if frame is not None:
                self.image_processor.set_image(frame)
                self.update_display()

    def load_image(self):
        """Load user selected image"""
        if self.current_source != "file":
            self.switch_to_file_source()
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "", "Image Files (*.png *.jpg *.jpeg *.bmp)"
        )
        if file_path:
            img = cv2.imread(file_path)
            if img is None:
                QMessageBox.warning(self, "Error", "Failed to load image")
                return
            self.image_processor.set_image(img)
            self.clear_roi()
            self.update_display()
            self.info_label.setText("Image loaded")

    def load_host_result(self):
        """Let the user select and load a BasicVIN result/config snapshot."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Result",
            HOST_BASICVIN_RESULTS_DIR,
            "JSON Files (*.json)",
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, dict):
                raise ValueError("result file is not a JSON object")

            # Debug results saved by this page wrap the configuration, while
            # Host BasicVIN results store it at the top level.
            saved_item = data.get("item")
            if isinstance(data.get("config"), dict):
                data = data["config"]

            item = saved_item if saved_item in BASICVIN_DEBUG_CONFIGS else None
            if item is None:
                target = data.get("target")
                item = next(
                    (
                        name
                        for name, config in BASICVIN_DEBUG_CONFIGS.items()
                        if config.get("target") == target
                    ),
                    None,
                )
            if item is None:
                filename = os.path.basename(path).lower()
                item = next(
                    (
                        name
                        for name, result_filename in BASICVIN_RESULT_FILES.items()
                        if filename == result_filename.lower()
                    ),
                    self.current_item,
                )
            if item != self.current_item:
                self.algo_combo.setCurrentText(item)

            target = BASICVIN_DEBUG_CONFIGS[self.current_item].get("target")
            merged = dict(BASICVIN_DEBUG_CONFIGS[self.current_item])
            merged.update(data)
            merged["target"] = target
            BASICVIN_DEBUG_CONFIGS[self.current_item] = merged
            detector = self._detectors[self.current_item]
            detector.config = dict(merged)

            roi = merged.get("roi")
            if isinstance(roi, dict):
                roi_rect = (
                    int(roi["x"]),
                    int(roi["y"]),
                    int(roi["width"]),
                    int(roi["height"]),
                )
                self.roi_selector.roi_rect = roi_rect
                self.image_processor.set_roi(roi_rect)
            elif roi == "full_image":
                self.roi_selector.clear()
                self.image_processor.set_roi(None)

            self._sync_hsv_controls()
            self.info_label.setText(f"Loaded result: {os.path.basename(path)}")
            self.detect_gray()
        except Exception as exc:
            QMessageBox.warning(self, "Load Result", f"Failed to load result:\n{exc}")

    def toggle_roi_selection(self):
        """Toggle ROI selection mode"""
        self.roi_enabled = self.roi_controls.roi_btn.isChecked()
        if self.roi_enabled:
            self.roi_controls.roi_btn.setText("Disable ROI Selection")
            self.info_label.setText("ROI ON - Click and drag on image")
        else:
            self.roi_controls.roi_btn.setText("Enable ROI Selection")
            self.info_label.setText("ROI OFF")

    def get_roi_mouse_press(self, event):
        """Handle mouse press for ROI selection"""
        if not self.roi_enabled or self.image_processor.original_image is None:
            return
        self.roi_selector.start_point = (event.pos().x(), event.pos().y())
        self.roi_selector.selecting = True

    def get_roi_mouse_move(self, event):
        """Handle mouse move for ROI selection"""
        if not self.roi_enabled or not self.roi_selector.selecting:
            return
        self.roi_selector.end_point = (event.pos().x(), event.pos().y())
        self.update_display_with_roi()

    def get_roi_mouse_release(self, event):
        """Handle mouse release for ROI selection"""
        if not self.roi_enabled or not self.roi_selector.selecting:
            return

        self.roi_selector.end_point = (event.pos().x(), event.pos().y())
        self.roi_selector.selecting = False

        roi = self.roi_selector.get_scaled_roi(
            self.roi_selector.start_point,
            self.roi_selector.end_point,
            (
                self.image_labels["Original Image"].width(),
                self.image_labels["Original Image"].height(),
            ),
            (IMAGE_WIDTH, IMAGE_HEIGHT),
        )

        if roi:
            self.roi_selector.roi_rect = roi
            self.image_processor.set_roi(roi)
            self.info_label.setText(f"ROI: {roi[0]},{roi[1]} {roi[2]}x{roi[3]}")
            self.detect_gray()
        else:
            self.info_label.setText("ROI too small")

        self.update_display()

    def update_display_with_roi(self):
        """Update display showing ROI selection rectangle"""
        if self.image_processor.original_image is None:
            return

        display_img = self.image_processor.original_image.copy()

        if (
            self.roi_selector.start_point
            and self.roi_selector.end_point
            and self.roi_selector.selecting
        ):

            label_width = self.image_labels["Original Image"].width()
            label_height = self.image_labels["Original Image"].height()

            scale_x = IMAGE_WIDTH / label_width if label_width > 0 else 1
            scale_y = IMAGE_HEIGHT / label_height if label_height > 0 else 1

            x1 = int(
                min(self.roi_selector.start_point[0], self.roi_selector.end_point[0])
                * scale_x
            )
            y1 = int(
                min(self.roi_selector.start_point[1], self.roi_selector.end_point[1])
                * scale_y
            )
            x2 = int(
                max(self.roi_selector.start_point[0], self.roi_selector.end_point[0])
                * scale_x
            )
            y2 = int(
                max(self.roi_selector.start_point[1], self.roi_selector.end_point[1])
                * scale_y
            )

            x1 = max(0, min(x1, IMAGE_WIDTH))
            y1 = max(0, min(y1, IMAGE_HEIGHT))
            x2 = max(0, min(x2, IMAGE_WIDTH))
            y2 = max(0, min(y2, IMAGE_HEIGHT))

            cv2.rectangle(display_img, (x1, y1), (x2, y2), (255, 192, 203), 2)

        self.display_image(display_img, "Original Image")

    def clear_roi(self):
        """Clear ROI selection"""
        self.roi_selector.clear()
        self.image_processor.set_roi(None)
        self.info_label.setText("ROI cleared")
        self.update_display()

    def use_full_image(self):
        """Use full image as ROI"""
        if self.image_processor.original_image is not None:
            self.roi_selector.roi_rect = (0, 0, IMAGE_WIDTH, IMAGE_HEIGHT)
            self.image_processor.set_roi((0, 0, IMAGE_WIDTH, IMAGE_HEIGHT))
            self.info_label.setText("Using full image")
            self.detect_gray()

    def on_threshold_changed(self):
        """Compatibility hook for older embedded callers."""
        if getattr(self, "_loading_hsv_params", False):
            return
        self.detect_gray()

    def save_debug_results(self):
        """Save current BasicVin debug images and detector config."""
        if not self._last_debug_images:
            QMessageBox.information(self, "Save Results", "Run detection before saving")
            return
        safe_item = "".join(
            ch if ch.isalnum() or ch in ("-", "_") else "_"
            for ch in str(self.current_item)
        )
        default_path = os.path.join(
            HOST_BASICVIN_RESULTS_DIR,
            f"{time.strftime('%Y%m%d_%H%M%S')}_{safe_item}_result.json",
        )
        result_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Result",
            default_path,
            "JSON Files (*.json)",
        )
        if not result_path:
            return
        if not result_path.lower().endswith(".json"):
            result_path += ".json"
        prefix = os.path.splitext(result_path)[0]
        if prefix.lower().endswith("_result"):
            prefix = prefix[:-7]
        try:
            for name, image in self._last_debug_images.items():
                if image is not None:
                    cv2.imwrite(f"{prefix}_{name}.png", image)
            payload = {
                "item": self.current_item,
                "config": self._current_debug_config(),
                "result": self._last_debug_result,
            }
            with open(result_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
            self.info_label.setText(f"Saved result: {os.path.basename(result_path)}")
        except Exception as exc:
            QMessageBox.warning(self, "Save Results", f"Failed to save results:\n{exc}")

    def _json_safe(self, value):
        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, np.generic):
            return value.item()
        if isinstance(value, dict):
            return {str(k): self._json_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._json_safe(item) for item in value]
        return value

    def _current_debug_config(self):
        config = dict(BASICVIN_DEBUG_CONFIGS[self.current_item])
        roi = self.roi_selector.roi_rect
        if roi:
            config["roi"] = {
                "x": int(roi[0]), "y": int(roi[1]),
                "width": int(roi[2]), "height": int(roi[3]),
            }
        config["hsv_thresholds"] = self.hsv_controls.get_params()
        return config

    def detect_gray(self):
        """Run the selected Host BasicVin detector on the current frame."""
        original = self.image_processor.original_image
        if original is None:
            return
        config = self._current_debug_config()

        if self.current_item == "HSV Debug":
            self.image_processor.set_algorithm("hsv")
            self.image_processor.set_params(config["hsv_thresholds"])
            result = self.image_processor.detect_gray()
            if not result or result[0] is None:
                return
            mask, x, y, width, height, detected, total, ratio = result
            original_display = self.image_processor.create_original_display(
                x, y, width, height
            )
            mask_display = self.image_processor.create_gray_detection(
                mask, x, y, width, height
            )
            preview = self.image_processor.create_roi_masked(
                mask, x, y, width, height
            )
            overlay = self.image_processor.create_overlay(
                mask, x, y, width, height
            )
            self.display_image(original_display, "Original Image")
            self.display_image(mask_display, "Detection Mask")
            self.display_image(preview, "ROI Region (Masked)")
            self.display_image(overlay, "Detection Overlay")
            self._last_debug_images = {
                "original": original_display,
                "mask": mask_display,
                "preview": preview,
                "overlay": overlay,
            }
            self._last_debug_result = {
                "detected_pixels": int(detected),
                "total_pixels": int(total),
                "gray_ratio_percent": round(float(ratio), 2),
            }
            self.info_label.setText(
                f"HSV Debug | detected {int(detected)}/{int(total)} px "
                f"({float(ratio):.2f}%)"
            )
            return

        detector = self._detectors[self.current_item]
        detector.config.update(config)
        result = detector.detect(original.copy()) or {}

        mask = np.zeros(original.shape[:2], dtype=np.uint8)
        overlay = original.copy()
        target_x = int(result.get("target_x", original.shape[1] // 2) or 0)
        target_y = int(result.get("target_y", original.shape[0] // 2) or 0)
        if self.current_item == "Feeder Chip Local":
            overlay = draw_feeder_debug(original, result)
            local = result.get("mask")
            region = result.get("feeder_roi") or {}
            if local is not None:
                x, y = int(region.get("x", 0)), int(region.get("y", 0))
                h = min(local.shape[0], mask.shape[0] - y)
                w = min(local.shape[1], mask.shape[1] - x)
                if h > 0 and w > 0:
                    mask[y:y + h, x:x + w] = local[:h, :w]
            else:
                for hole in result.get("feeder_holes", []):
                    cv2.circle(
                        mask,
                        (int(hole["x"]), int(hole["y"])),
                        max(1, int(hole["r"])),
                        255,
                        -1,
                    )
                pocket = np.asarray(
                    [
                        (int(point["x"]), int(point["y"]))
                        for point in result.get("feeder_pocket", [])
                    ],
                    dtype=np.int32,
                )
                if len(pocket) >= 3:
                    cv2.fillPoly(mask, [pocket], 255)
        elif result.get("found", False):
            cv2.circle(overlay, (target_x, target_y), 7, (0, 255, 0), 2)
            cv2.drawMarker(overlay, (target_x, target_y), (0, 255, 255),
                           cv2.MARKER_CROSS, 18, 1)
            if self.current_item == "PCB Board Local":
                corners = result.get("board_corners") or []
                points = np.array([(int(p["x"]), int(p["y"])) for p in corners], dtype=np.int32)
                if len(points) >= 2:
                    cv2.polylines(overlay, [points], True, (255, 80, 0), 2)
            elif self.current_item == "Bottom Camera Recheck Pick":
                box = result.get("box") or []
                if len(box) >= 4:
                    cv2.polylines(overlay, [np.array(box, dtype=np.int32)], True, (0, 200, 255), 2)

        mask_bgr = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        roi_masked = cv2.bitwise_and(original, original, mask=mask)
        self.display_image(original, "Original Image")
        self.display_image(mask_bgr, "Detection Mask")
        self.display_image(roi_masked, "ROI Region (Masked)")
        self.display_image(overlay, "Detection Overlay")
        self._last_debug_images = {
            "original": original,
            "mask": mask_bgr,
            "roi_masked": roi_masked,
            "overlay": overlay,
        }
        self._last_debug_result = {
            key: self._json_safe(value)
            for key, value in result.items()
            if key not in {"mask"}
        }
        if result.get("found", False):
            self.info_label.setText(
                f"{self.current_item} | found | "
                f"offset=({float(result.get('offset_x', 0)):+.1f},"
                f"{float(result.get('offset_y', 0)):+.1f}) px"
            )
        else:
            self.info_label.setText(
                f"{self.current_item} | not found | {result.get('message', '')}"
            )

    def display_image(self, img, title):
        """Display image in specified label - keep aspect ratio with black padding"""
        if img is None:
            return

        label = self.image_labels[title]
        target_width = label.width()
        target_height = label.height()
        
        if target_width <= 0 or target_height <= 0:
            target_width = 400
            target_height = 300
        
        # Get original image dimensions
        img_h, img_w = img.shape[:2]
        
        # Calculate scaling to fit within target while keeping aspect ratio
        scale_w = target_width / img_w
        scale_h = target_height / img_h
        scale = min(scale_w, scale_h)
        
        # Calculate new dimensions
        new_w = int(img_w * scale)
        new_h = int(img_h * scale)
        
        # Resize image
        resized_img = cv2.resize(img, (new_w, new_h))
        
        # Create black canvas of target size
        canvas = np.zeros((target_height, target_width, 3), dtype=np.uint8)
        
        # Calculate position to center the image
        x_offset = (target_width - new_w) // 2
        y_offset = (target_height - new_h) // 2
        
        # Place resized image on canvas
        canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized_img
        
        # Convert to QImage and display
        rgb_image = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        label.setPixmap(QPixmap.fromImage(qt_image))

    def update_display(self):
        """Update all displays"""
        if self.image_processor.original_image is not None:
            self.detect_gray()

    def closeEvent(self, event):
        """Handle application close"""
        self.stop_mjpeg_stream()
        event.accept()
