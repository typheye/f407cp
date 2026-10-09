#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
******************************************************************************
* @file    roi_selector.py
* @author  JanPNP Development Team
* @brief   ROI selection state manager
*          Provides mouse-driven region of interest selection with drag,
*          resize, and clear operations for image analysis.
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
class ROISelector:
    """ROI selection state manager"""
    def __init__(self):
        self.start_point = None
        self.end_point = None
        self.roi_rect = None
        self.selecting = False
        
    def clear(self):
        """Clear all selection data"""
        self.start_point = None
        self.end_point = None
        self.roi_rect = None
        self.selecting = False
        
    def get_scaled_roi(self, click_start, click_end, display_size, image_size):
        """
        Convert mouse coordinates to image coordinates
        display_size: (width, height) of display area
        image_size: (width, height) of original image
        """
        if not click_start or not click_end:
            return None
            
        scale_x = image_size[0] / display_size[0]
        scale_y = image_size[1] / display_size[1]
        
        # Get rectangle coordinates
        x1 = min(click_start[0], click_end[0])
        y1 = min(click_start[1], click_end[1])
        x2 = max(click_start[0], click_end[0])
        y2 = max(click_start[1], click_end[1])
        
        # Clamp to display boundaries
        x1 = max(0, min(x1, display_size[0]))
        y1 = max(0, min(y1, display_size[1]))
        x2 = max(0, min(x2, display_size[0]))
        y2 = max(0, min(y2, display_size[1]))
        
        # Scale to image coordinates
        roi_x = int(x1 * scale_x)
        roi_y = int(y1 * scale_y)
        roi_w = int((x2 - x1) * scale_x)
        roi_h = int((y2 - y1) * scale_y)
        
        # Ensure ROI is within image boundaries
        roi_w = min(roi_w, image_size[0] - roi_x)
        roi_h = min(roi_h, image_size[1] - roi_y)
        
        if roi_w > 5 and roi_h > 5:
            return (roi_x, roi_y, roi_w, roi_h)
        return None