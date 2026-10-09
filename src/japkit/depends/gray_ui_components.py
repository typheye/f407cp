#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
******************************************************************************
* @file    ui_components.py
* @author  JanPNP Development Team
* @brief   PyQt5 UI component definitions
*          Provides reusable UI widget factories and custom controls
*          for the gray detector application interface.
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
from PyQt5.QtWidgets import (
    QGroupBox,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QPushButton,
    QComboBox,
    QCheckBox,
    QSpinBox,
    QWidget,
)
from PyQt5.QtCore import Qt


class FileControlGroup(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Load Result", parent)
        layout = QVBoxLayout()

        self.load_btn = QPushButton("Load Result")
        self.save_btn = QPushButton("Save Result")

        layout.addWidget(self.load_btn)
        layout.addWidget(self.save_btn)
        self.setLayout(layout)


class ROIControlGroup(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("ROI Selection", parent)
        layout = QVBoxLayout()

        self.roi_btn = QPushButton("Enable ROI Selection")
        self.roi_btn.setCheckable(True)
        self.clear_btn = QPushButton("Clear ROI")
        self.full_btn = QPushButton("Use Full Image")

        layout.addWidget(self.roi_btn)
        layout.addWidget(self.clear_btn)
        layout.addWidget(self.full_btn)
        self.setLayout(layout)


class SliderWithSpinBox(QWidget):
    """Slider with spinbox for precise adjustment"""

    def __init__(self, label_text, min_val, max_val, init_min, init_max, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.is_range = True

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Label
        self.label = QLabel(label_text)
        layout.addWidget(self.label)

        # Min row
        min_layout = QHBoxLayout()
        min_layout.addWidget(QLabel("Min:"))
        self.min_slider = QSlider(Qt.Horizontal)
        self.min_slider.setRange(min_val, max_val)
        self.min_slider.setValue(init_min)
        self.min_spin = QSpinBox()
        self.min_spin.setRange(min_val, max_val)
        self.min_spin.setValue(init_min)
        self.min_spin.setFixedWidth(50)

        # Min buttons
        self.min_minus_btn = QPushButton("-1")
        self.min_minus_btn.setFixedWidth(30)
        self.min_plus_btn = QPushButton("+1")
        self.min_plus_btn.setFixedWidth(30)

        min_layout.addWidget(self.min_minus_btn)
        min_layout.addWidget(self.min_slider)
        min_layout.addWidget(self.min_spin)
        min_layout.addWidget(self.min_plus_btn)

        # Max row
        max_layout = QHBoxLayout()
        max_layout.addWidget(QLabel("Max:"))
        self.max_slider = QSlider(Qt.Horizontal)
        self.max_slider.setRange(min_val, max_val)
        self.max_slider.setValue(init_max)
        self.max_spin = QSpinBox()
        self.max_spin.setRange(min_val, max_val)
        self.max_spin.setValue(init_max)
        self.max_spin.setFixedWidth(50)

        # Max buttons
        self.max_minus_btn = QPushButton("-1")
        self.max_minus_btn.setFixedWidth(30)
        self.max_plus_btn = QPushButton("+1")
        self.max_plus_btn.setFixedWidth(30)

        max_layout.addWidget(self.max_minus_btn)
        max_layout.addWidget(self.max_slider)
        max_layout.addWidget(self.max_spin)
        max_layout.addWidget(self.max_plus_btn)

        layout.addLayout(min_layout)
        layout.addLayout(max_layout)
        self.setLayout(layout)

        # Connect signals
        self.min_slider.valueChanged.connect(self.on_min_slider_changed)
        self.min_spin.valueChanged.connect(self.on_min_spin_changed)
        self.min_minus_btn.clicked.connect(
            lambda: self.min_slider.setValue(self.min_slider.value() - 1)
        )
        self.min_plus_btn.clicked.connect(
            lambda: self.min_slider.setValue(self.min_slider.value() + 1)
        )

        self.max_slider.valueChanged.connect(self.on_max_slider_changed)
        self.max_spin.valueChanged.connect(self.on_max_spin_changed)
        self.max_minus_btn.clicked.connect(
            lambda: self.max_slider.setValue(self.max_slider.value() - 1)
        )
        self.max_plus_btn.clicked.connect(
            lambda: self.max_slider.setValue(self.max_slider.value() + 1)
        )

    def on_min_slider_changed(self, value):
        self.min_spin.setValue(value)
        if self.parent:
            self.parent.on_threshold_changed()

    def on_min_spin_changed(self, value):
        self.min_slider.setValue(value)

    def on_max_slider_changed(self, value):
        self.max_spin.setValue(value)
        if self.parent:
            self.parent.on_threshold_changed()

    def on_max_spin_changed(self, value):
        self.max_slider.setValue(value)

    def get_min(self):
        return self.min_slider.value()

    def get_max(self):
        return self.max_slider.value()


class HSVControlGroup(QGroupBox):
    """HSV-based gray detection (simpler and more intuitive)"""

    def __init__(self, parent=None):
        super().__init__("HSV Thresholds (Recommended)", parent)
        self.parent = parent
        layout = QVBoxLayout()

        # Saturation channel - KEY for grayscale detection
        self.s_control = SliderWithSpinBox(
            "Saturation (S) - Lower = More Gray", 0, 255, 0, 30, self
        )
        layout.addWidget(self.s_control)

        # Value channel (brightness)
        self.v_control = SliderWithSpinBox(
            "Value (V) - Brightness", 0, 255, 0, 255, self
        )
        layout.addWidget(self.v_control)

        # Invert checkbox
        invert_layout = QHBoxLayout()
        self.invert_checkbox = QCheckBox(
            "Invert Detection (White->Black, Black->White)"
        )
        self.invert_checkbox.stateChanged.connect(self.on_invert_changed)
        invert_layout.addWidget(self.invert_checkbox)
        invert_layout.addStretch()
        layout.addLayout(invert_layout)

        self.setLayout(layout)

    def on_invert_changed(self):
        if self.parent:
            self.parent.on_threshold_changed()

    def on_threshold_changed(self):
        if self.parent:
            self.parent.on_threshold_changed()

    def get_params(self):
        return {
            "S_min": self.s_control.get_min(),
            "S_max": self.s_control.get_max(),
            "V_min": self.v_control.get_min(),
            "V_max": self.v_control.get_max(),
            "invert": self.invert_checkbox.isChecked(),
        }

    def set_params(self, params):
        """Set parameters from saved values"""
        if "S_min" in params:
            self.s_control.min_slider.setValue(params["S_min"])
        if "S_max" in params:
            self.s_control.max_slider.setValue(params["S_max"])
        if "V_min" in params:
            self.v_control.min_slider.setValue(params["V_min"])
        if "V_max" in params:
            self.v_control.max_slider.setValue(params["V_max"])
        if "invert" in params:
            self.invert_checkbox.setChecked(params["invert"])


class LABControlGroup(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("LAB Thresholds (Advanced)", parent)
        self.parent = parent
        layout = QVBoxLayout()

        # L channel
        self.l_control = SliderWithSpinBox(
            "L Channel (Brightness)", 0, 100, 0, 100, self
        )
        layout.addWidget(self.l_control)

        # A channel
        self.a_control = SliderWithSpinBox(
            "A Channel (Green-Red)", -128, 127, -10, 10, self
        )
        layout.addWidget(self.a_control)

        # B channel
        self.b_control = SliderWithSpinBox(
            "B Channel (Blue-Yellow)", -128, 127, -10, 10, self
        )
        layout.addWidget(self.b_control)

        self.setLayout(layout)

    def on_threshold_changed(self):
        if self.parent:
            self.parent.on_threshold_changed()

    def get_params(self):
        return {
            "L_min": self.l_control.get_min(),
            "L_max": self.l_control.get_max(),
            "A_min": self.a_control.get_min(),
            "A_max": self.a_control.get_max(),
            "B_min": self.b_control.get_min(),
            "B_max": self.b_control.get_max(),
        }

    def set_params(self, params):
        """Set parameters from saved values"""
        if "L_min" in params:
            self.l_control.min_slider.setValue(params["L_min"])
        if "L_max" in params:
            self.l_control.max_slider.setValue(params["L_max"])
        if "A_min" in params:
            self.a_control.min_slider.setValue(params["A_min"])
        if "A_max" in params:
            self.a_control.max_slider.setValue(params["A_max"])
        if "B_min" in params:
            self.b_control.min_slider.setValue(params["B_min"])
        if "B_max" in params:
            self.b_control.max_slider.setValue(params["B_max"])
