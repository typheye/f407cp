#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
******************************************************************************
* @file    config.py
* @author  JanPNP Development Team
* @brief   Image settings and LAB threshold configuration
*          Provides image dimension settings, LAB color space thresholds,
*          and default configuration parameters for the gray detector tool.
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
import os

# Image settings
IMAGE_WIDTH = 640
IMAGE_HEIGHT = 480
DISPLAY_WIDTH = 320
DISPLAY_HEIGHT = 240

# Default LAB thresholds (narrow range for grayscale)
DEFAULT_LAB_THRESHOLDS = {
    'L_min': 0,
    'L_max': 100,
    'A_min': -10,
    'A_max': 10,
    'B_min': -10,
    'B_max': 10
}

# Default HSV thresholds (easier for grayscale detection)
DEFAULT_HSV_THRESHOLDS = {
    'S_min': 0,
    'S_max': 30,      # Low saturation = grayscale
    'V_min': 0,
    'V_max': 255
}

# File paths
DEFAULT_IMAGE_PATH = "./test.png"
RESULTS_FILE_NAME = "detection_result.json"

# Color constants (BGR)
COLOR_GREEN = (0, 255, 0)
COLOR_WHITE = (255, 255, 255)
COLOR_BLACK = (0, 0, 0)

# UI settings
WINDOW_MIN_WIDTH = 1200
WINDOW_MIN_HEIGHT = 800
CONTROL_PANEL_WIDTH = 320
DISPLAY_LABEL_SIZE = (320, 240)