#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
******************************************************************************
* @file    image_processor.py
* @author  JanPNP Development Team
* @brief   Image processor for ROI selection and analysis
*          Provides image loading, resizing, ROI selection, and color space
*          analysis for the gray detector tool.
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
import cv2
import numpy as np
from depends.config import IMAGE_WIDTH, IMAGE_HEIGHT


class ImageProcessor:
    def __init__(self):
        self.original_image = None
        self.roi_rect = None
        self.params = None
        self.algorithm = "hsv"  # "hsv" or "lab"
        
    def set_image(self, image):
        """Set and resize image to standard size"""
        if image is not None:
            self.original_image = cv2.resize(image, (IMAGE_WIDTH, IMAGE_HEIGHT))
        else:
            self.original_image = None
            
    def set_roi(self, roi_rect):
        """Set ROI rectangle"""
        self.roi_rect = roi_rect
        
    def set_params(self, params):
        """Set detection parameters"""
        self.params = params
        
    def set_algorithm(self, algorithm):
        """Set detection algorithm: 'hsv' or 'lab'"""
        self.algorithm = algorithm
        
    def detect_gray(self):
        """Detect gray areas based on selected algorithm"""
        if self.original_image is None or self.params is None:
            return None, None, None, None, 0, 0
            
        # Get ROI
        if self.roi_rect:
            x, y, w, h = self.roi_rect
            # Ensure ROI is within image boundaries
            x = max(0, min(x, IMAGE_WIDTH))
            y = max(0, min(y, IMAGE_HEIGHT))
            w = min(w, IMAGE_WIDTH - x)
            h = min(h, IMAGE_HEIGHT - y)
            if w <= 0 or h <= 0:
                x, y, w, h = 0, 0, IMAGE_WIDTH, IMAGE_HEIGHT
            roi_img = self.original_image[y:y+h, x:x+w]
        else:
            roi_img = self.original_image
            x, y, w, h = 0, 0, IMAGE_WIDTH, IMAGE_HEIGHT
            
        if self.algorithm == "hsv":
            # HSV-based detection (simpler)
            hsv_img = cv2.cvtColor(roi_img, cv2.COLOR_BGR2HSV)
            H, S, V = cv2.split(hsv_img)
            
            S_min = self.params.get('S_min', 0)
            S_max = self.params.get('S_max', 30)
            V_min = self.params.get('V_min', 0)
            V_max = self.params.get('V_max', 255)
            
            mask = (S >= S_min) & (S <= S_max) & (V >= V_min) & (V <= V_max)
            if self.params.get('invert', False):
                mask = ~mask
        else:
            # LAB-based detection (more precise)
            lab_img = cv2.cvtColor(roi_img, cv2.COLOR_BGR2LAB)
            L, A, B = cv2.split(lab_img)
            
            L_min = self.params.get('L_min', 0)
            L_max = self.params.get('L_max', 100)
            A_min = self.params.get('A_min', -10)
            A_max = self.params.get('A_max', 10)
            B_min = self.params.get('B_min', -10)
            B_max = self.params.get('B_max', 10)
            
            mask = (L >= L_min) & (L <= L_max) & \
                   (A >= A_min) & (A <= A_max) & \
                   (B >= B_min) & (B <= B_max)
        
        # Calculate statistics
        total_pixels = mask.size
        detected_pixels = np.sum(mask)
        gray_ratio = (detected_pixels / total_pixels) * 100 if total_pixels > 0 else 0
        
        return mask, x, y, w, h, detected_pixels, total_pixels, gray_ratio
        
    def create_original_display(self, x, y, w, h):
        """Create original image with ROI rectangle"""
        if self.original_image is None:
            return None
            
        display = self.original_image.copy()
        if self.roi_rect:
            cv2.rectangle(display, (x, y), (x+w, y+h), (255, 192, 203), 2)
        return display
        
    def create_gray_detection(self, mask, x, y, w, h):
        """Create black image with white detected pixels"""
        if self.original_image is None:
            return None
            
        gray_detection = np.zeros((IMAGE_HEIGHT, IMAGE_WIDTH, 3), dtype=np.uint8)
        
        if mask is not None and len(mask) > 0:
            # Ensure mask dimensions match
            if mask.shape[0] == h and mask.shape[1] == w:
                white_result = np.zeros((h, w, 3), dtype=np.uint8)
                white_result[mask] = [255, 255, 255]
                gray_detection[y:y+h, x:x+w] = white_result
        
        if self.roi_rect:
            cv2.rectangle(gray_detection, (x, y), (x+w, y+h), (255, 192, 203), 2)
            
        return gray_detection

    def create_roi_masked(self, mask, x, y, w, h):
        """Show original image with detected region contour (green rectangle for rectangular shapes with ID label)"""
        if self.original_image is None:
            return None
            
        # Start with original image copy
        roi_masked = self.original_image.copy()
        
        # Draw ROI rectangle if exists (pink)
        if self.roi_rect:
            cv2.rectangle(roi_masked, (x, y), (x+w, y+h), (255, 192, 203), 2)
        
        # Find contours of detected mask
        if mask is not None and len(mask) > 0 and mask.shape[0] == h and mask.shape[1] == w:
            # Convert mask to uint8 for contour detection
            mask_uint8 = mask.astype(np.uint8) * 255
            
            # Find contours
            contours, _ = cv2.findContours(mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            contour_id = 1  # Counter for labeling
            for contour in contours:
                if len(contour) < 3:  # Skip invalid contours
                    continue
                    
                # Adjust contour coordinates to full image
                contour[:, :, 0] += x
                contour[:, :, 1] += y
                
                # Calculate contour perimeter and area
                perimeter = cv2.arcLength(contour, True)
                area = cv2.contourArea(contour)
                
                if area < 50:  # Skip tiny contours (noise)
                    continue
                
                # Approximate polygon
                epsilon = 0.02 * perimeter
                approx = cv2.approxPolyDP(contour, epsilon, True)
                
                # Check if shape is close to rectangle (4 points and area ratio)
                # Check if shape is close to rectangle (4 points and area ratio)
                if len(approx) == 4:
                    # Calculate bounding rectangle
                    rect = cv2.boundingRect(contour)
                    rect_x, rect_y, rect_w, rect_h = rect
                    
                    # Draw green rectangle
                    cv2.rectangle(roi_masked, (rect_x, rect_y), (rect_x + rect_w, rect_y + rect_h), (0, 255, 0), 2)
                    
                    # Add ID label ABOVE the rectangle
                    label = f"ID:{contour_id}"
                    
                    # Get text size
                    (text_w, text_h), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
                    
                    # Position label above the rectangle
                    label_x = rect_x + 5
                    label_y = rect_y - 5
                    
                    # If label would go above image boundary, put it inside at top
                    if label_y - text_h < 0:
                        label_y = rect_y + text_h + 5
                    
                    # Draw semi-transparent background
                    cv2.rectangle(roi_masked, 
                                (label_x - 2, label_y - text_h - 2),
                                (label_x + text_w + 2, label_y + 2),
                                (0, 0, 0), -1)
                    
                    # Draw text
                    cv2.putText(roi_masked, label, (label_x, label_y), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                    
                    contour_id += 1
                else:
                    # For non-rectangular shapes
                    for i, point in enumerate(contour):
                        pt = tuple(point[0])
                        cv2.circle(roi_masked, pt, 2, (0, 255, 255), -1)
                        next_pt = tuple(contour[(i + 1) % len(contour)][0])
                        cv2.line(roi_masked, pt, next_pt, (0, 255, 255), 1)
                    cv2.drawContours(roi_masked, [contour], -1, (0, 255, 255), 1)
                    
                    # Add ID label above the contour
                    rect = cv2.boundingRect(contour)
                    rect_x, rect_y, rect_w, rect_h = rect
                    
                    contour_id += 1
        
        return roi_masked

    def create_overlay(self, mask, x, y, w, h):
        """Create green overlay on detected areas"""
        if self.original_image is None:
            return None
            
        full_mask = np.zeros((IMAGE_HEIGHT, IMAGE_WIDTH), dtype=np.uint8)
        
        if mask is not None and len(mask) > 0:
            if mask.shape[0] == h and mask.shape[1] == w:
                full_mask[y:y+h, x:x+w] = mask
        
        green_overlay = np.zeros((IMAGE_HEIGHT, IMAGE_WIDTH, 3), dtype=np.uint8)
        green_overlay[full_mask == 1] = [0, 255, 0]
        
        overlay_result = cv2.addWeighted(self.original_image, 0.6, green_overlay, 0.4, 0)
        
        if self.roi_rect:
            cv2.rectangle(overlay_result, (x, y), (x+w, y+h), (255, 192, 203), 2)
            
        return overlay_result
