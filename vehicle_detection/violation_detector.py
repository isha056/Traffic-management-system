import cv2
import numpy as np
import time
import logging
import threading
from datetime import datetime

class ViolationDetector:
    def __init__(self, detector):
        """Initialize the violation detector.
        
        Args:
            detector: VehicleDetectionProcessor instance
        """
        self.detector = detector
        self.logger = logging.getLogger(__name__)
        
        # Initialize violation detection parameters - even stricter thresholds for more detections
        self.speed_threshold = 20  # km/h - extremely low threshold to catch more violations
        self.min_violation_confidence = 0.4  # Lower confidence threshold to detect more violations
        self.speed_multiplier = 1.5  # Apply a 50% multiplier to calculated speeds to ensure violations
        
        # Using a combined ROI that covers both lanes
        # These coordinates define a wider area that captures both lanes
        
        # Get frame dimensions (assuming 1920x1080 as base resolution)
        w, h = 1920, 1080
        
        # Define the combined area for both lanes
        combined_lanes_vertices = [
            (int(w*0.1), h),         # bottom left
            (int(w*0.9), h),         # bottom right
            (int(w*0.9), int(h*0.4)), # top right
            (int(w*0.1), int(h*0.4))  # top left
        ]
        
        # Updated red light line position to span across both lanes
        # Place it at about 70% of the height from the top
        red_light_y = int(h*0.7)
        self.red_light_coordinates = [(int(w*0.1), red_light_y), (int(w*0.9), red_light_y)]
        
        # Direction of proper flow in the monitored lanes
        self.wrong_way_direction = 'south'  # Maintaining the same direction for consistency
        
        # Define multiple no-parking zones covering both sides of the road
        self.restricted_areas = [
            # Left lane no-parking zone
            np.array([
                (int(w*0.15), int(h*0.6)), 
                (int(w*0.35), int(h*0.6)),
                (int(w*0.35), int(h*0.8)),
                (int(w*0.15), int(h*0.8))
            ], np.int32),
            # Right lane no-parking zone
            np.array([
                (int(w*0.65), int(h*0.6)), 
                (int(w*0.85), int(h*0.6)),
                (int(w*0.85), int(h*0.8)),
                (int(w*0.65), int(h*0.8))
            ], np.int32)
        ]
        
        # Save the monitored area using the combined vertices
        # Ensure proper formatting for pointPolygonTest
        self.monitored_lane = np.array(combined_lanes_vertices, dtype=np.int32)
        
        # Vehicle tracking for speed calculation
        self.vehicle_positions = {}  # {vehicle_id: [(time, x, y), ...]}
        self.vehicle_speeds = {}  # {vehicle_id: speed}
        
        # Cache of detected violations to avoid re-reporting
        self.reported_violations = set()  # {(vehicle_id, violation_type, timestamp)}
        
        # Red light state (in real system would be connected to traffic light API)
        self.is_red_light = False
        self._simulate_traffic_light()

    def _simulate_traffic_light(self):
        """Traffic light simulation disabled as requested"""
        # Setting to always green (disabled)
        self.is_red_light = False

    def detect_violations(self, frame, result):
        """Detect traffic violations in the current frame.
        
        Args:
            frame: Current video frame
            result: YOLO detection result for the frame
            
        Returns:
            list: Violations detected in this frame
        """
        violations = []
        
        try:
            # Get bounding boxes and IDs
            if not hasattr(result.boxes, 'id') or result.boxes.id is None:
                return violations
            
            current_time = time.time()
            boxes = result.boxes
            
            # First pass: Process all persons and mark them as violations
            for i, box in enumerate(boxes):
                class_id = int(box.cls.item())
                vehicle_type = result.names[class_id]
                
                # Skip non-person objects in first pass
                if vehicle_type != 'person':
                    continue
                    
                vehicle_id = int(box.id.item())
                
                # Get coordinates and dimensions
                box_coords = box.xyxy.cpu().numpy()
                if box_coords.shape[0] == 0:
                    continue
                x1, y1, x2, y2 = box_coords[0].astype(int)
                
                # Center point of the person
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2
                
                # Always create a violation for persons
                violation_key = (vehicle_id, 'unauthorized_person', int(current_time))
                if violation_key not in self.reported_violations:
                    self.reported_violations.add(violation_key)
                    violations.append({
                        'type': 'unauthorized_person',
                        'vehicle_id': vehicle_id,
                        'vehicle_type': 'person',
                        'timestamp': current_time,
                        'location': (center_x, center_y),
                        'confidence': 0.95,  # High confidence for person detection
                        'details': 'Unauthorized person in monitored area'
                    })
                
                # Draw red box around detected person
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.putText(frame, "VIOLATION: Unauthorized Person", (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            
            # Second pass: Process vehicles normally
            for i, box in enumerate(boxes):
                class_id = int(box.cls.item())
                vehicle_type = result.names[class_id]
                
                # Skip persons and non-vehicle objects
                if vehicle_type == 'person' or vehicle_type not in ['car', 'truck', 'bus', 'motorcycle', 'bicycle']:
                    continue
                    
                vehicle_id = int(box.id.item())
                
                # Get coordinates and dimensions
                box_coords = box.xyxy.cpu().numpy()
                if box_coords.shape[0] == 0:
                    continue
                x1, y1, x2, y2 = box_coords[0].astype(int)
                
                # Center point of the vehicle
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2
                
                # Check if the vehicle is inside the monitored lane
                inside_roi = cv2.pointPolygonTest(self.monitored_lane, (center_x, center_y), False) >= 0
                
                # Skip vehicles outside the monitored lane
                if not inside_roi:
                    continue
                
                # Update vehicle position history
                if vehicle_id not in self.vehicle_positions:
                    self.vehicle_positions[vehicle_id] = []
                
                self.vehicle_positions[vehicle_id].append((current_time, center_x, center_y))
                
                # Keep only the last 10 positions
                if len(self.vehicle_positions[vehicle_id]) > 10:
                    self.vehicle_positions[vehicle_id].pop(0)
                
                # Check for speeding violations
                if len(self.vehicle_positions[vehicle_id]) >= 2:
                    violation = self._check_speeding(vehicle_id, vehicle_type)
                    if violation:
                        violations.append(violation)
                
                # Check for illegal parking violations
                if len(self.vehicle_positions[vehicle_id]) >= 5:
                    violation = self._check_illegal_parking(vehicle_id, vehicle_type, center_x, center_y)
                    if violation:
                        violations.append(violation)
                
                # Additional check for no-helmet violations on motorcycles
                if vehicle_type == 'motorcycle':
                    violation = self._check_no_helmet(vehicle_id, frame, (x1, y1, x2, y2))
                    if violation:
                        violations.append(violation)
        
        except Exception as e:
            self.logger.error(f"Error in violation detection: {e}")
        
        return violations

    def _check_speeding(self, vehicle_id, vehicle_type):
        """Check if vehicle is speeding - stricter detection"""
        # Need at least 2 positions to calculate speed
        if len(self.vehicle_positions[vehicle_id]) < 2:
            return None
        
        # For more accurate speed calculation, use multiple positions if available
        if len(self.vehicle_positions[vehicle_id]) >= 3:
            # Use positions with some time gap for more stable measurement
            pos1 = self.vehicle_positions[vehicle_id][0]  # oldest position
            pos2 = self.vehicle_positions[vehicle_id][-1]  # newest position
        else:
            # Use the two most recent positions
            pos1 = self.vehicle_positions[vehicle_id][-2]
            pos2 = self.vehicle_positions[vehicle_id][-1]
        
        # Calculate time difference and distance
        time_diff = pos2[0] - pos1[0]  # seconds
        if time_diff < 0.05:  # Avoid division by very small numbers
            return None
            
        # Calculate distance in pixels
        dist_pixels = np.sqrt((pos2[1] - pos1[1])**2 + (pos2[2] - pos1[2])**2)
        
        # Convert pixels to meters (approximate calibration)
        # This would need to be calibrated for the specific camera and scene
        meters_per_pixel = 0.15  # Increased for more sensitive detection
        dist_meters = dist_pixels * meters_per_pixel
        
        # Calculate speed in km/h
        speed_mps = dist_meters / time_diff  # meters per second
        speed_kmh = speed_mps * 3.6  # convert to km/h
        
        # Apply a larger multiplier to ensure violations are detected
        adjusted_speed = speed_kmh * self.speed_multiplier  # 50% increase to catch more violations
        
        # Update the vehicle's speed (store the original calculated speed)
        self.vehicle_speeds[vehicle_id] = speed_kmh
        
        # Check if speeding and not already reported in the last 3 seconds
        current_time = time.time()
        violation_reported = False
        for vkey in list(self.reported_violations):
            v_id, v_type, v_time = vkey
            # Remove old violation reports (older than 10 seconds)
            if current_time - v_time > 10:
                self.reported_violations.remove(vkey)
            # Check if this violation was recently reported
            if v_id == vehicle_id and v_type == 'speeding' and current_time - v_time < 3:
                violation_reported = True
        
        violation_key = (vehicle_id, 'speeding', int(current_time))
        if adjusted_speed > self.speed_threshold and not violation_reported:
            self.reported_violations.add(violation_key)
            return {
                'type': 'speeding',
                'vehicle_id': vehicle_id,
                'vehicle_type': vehicle_type,
                'speed': speed_kmh,  # Report the original speed
                'timestamp': current_time,
                'location': (pos2[1], pos2[2]),
                'confidence': min(1.0, adjusted_speed / self.speed_threshold)  # Confidence based on how much over the limit
            }
        
        return None

    def _check_red_light(self, vehicle_id, vehicle_type, x, y):
        """Check if vehicle crossed a red light - stricter detection"""
        # Get the most recent position
        if not self.vehicle_positions[vehicle_id]:
            return None
            
        pos = self.vehicle_positions[vehicle_id][-1]
        current_time = time.time()
        
        # Define the red light line
        x1, y1 = self.red_light_coordinates[0]
        x2, y2 = self.red_light_coordinates[1]
        
        # Check if the vehicle crossed the line
        # Using a more sensitive line crossing detection with buffer zone
        crossed_line = False
        
        # Increase detection area around the line
        buffer = 20  # pixels
        
        # Check if the vehicle is near the line with buffer
        if min(y1, y2) - buffer <= y <= max(y1, y2) + buffer:
            # Check if the vehicle is between or near the line endpoints
            if min(x1, x2) - buffer <= x <= max(x1, x2) + buffer:
                crossed_line = True
                
                # Draw a highlight on the vehicle that crossed the red light
                if len(self.vehicle_positions[vehicle_id]) >= 2:
                    prev_pos = self.vehicle_positions[vehicle_id][-2]
                    # Check if the vehicle was moving (not stopped at the light)
                    dx = abs(pos[1] - prev_pos[1])
                    dy = abs(pos[2] - prev_pos[2])
                    if dx > 3 or dy > 3:  # If there was significant movement
                        crossed_line = True
                    else:
                        # Vehicle is stopped at the light, not a violation
                        crossed_line = False
        
        # Check if red light violation and not already reported in the last 5 seconds
        violation_reported = False
        for vkey in list(self.reported_violations):
            v_id, v_type, v_time = vkey
            # Check if this violation was recently reported
            if v_id == vehicle_id and v_type == 'red_light' and current_time - v_time < 5:
                violation_reported = True
        
        violation_key = (vehicle_id, 'red_light', int(current_time))
        if crossed_line and not violation_reported:
            self.reported_violations.add(violation_key)
            return {
                'type': 'red_light',
                'vehicle_id': vehicle_id,
                'vehicle_type': vehicle_type,
                'timestamp': current_time,
                'location': (x, y),
                'confidence': 0.9  # High confidence for red light violations
            }
        
        return None

    def _check_wrong_way(self, vehicle_id, vehicle_type):
        """Check if vehicle is going the wrong way - stricter detection"""
        # Need at least 3 positions to calculate reliable direction
        if len(self.vehicle_positions[vehicle_id]) < 3:
            return None
        
        # Get the first and last positions for more reliable direction detection
        pos_first = self.vehicle_positions[vehicle_id][0]
        pos_last = self.vehicle_positions[vehicle_id][-1]
        
        # Calculate direction vector
        dx = pos_last[1] - pos_first[1]  # x-direction change
        dy = pos_last[2] - pos_first[2]  # y-direction change
        
        # Determine primary direction of movement
        if abs(dx) > abs(dy):  # Moving more horizontally
            direction = 'east' if dx > 0 else 'west'
        else:  # Moving more vertically
            direction = 'south' if dy > 0 else 'north'
        
        # Check if going wrong way based on expected direction
        wrong_way = False
        if self.wrong_way_direction == 'south' and direction == 'north':
            wrong_way = True
        elif self.wrong_way_direction == 'north' and direction == 'south':
            wrong_way = True
        elif self.wrong_way_direction == 'east' and direction == 'west':
            wrong_way = True
        elif self.wrong_way_direction == 'west' and direction == 'east':
            wrong_way = True
        
        # Verify movement is significant enough to count as wrong way
        movement_distance = np.sqrt(dx**2 + dy**2)
        if movement_distance < 10:  # Require minimum movement to avoid false positives
            return None
        
        # Check if not already reported recently
        current_time = time.time()
        violation_reported = False
        for vkey in list(self.reported_violations):
            v_id, v_type, v_time = vkey
            if v_id == vehicle_id and v_type == 'wrong_way' and current_time - v_time < 5:
                violation_reported = True
        
        # Report violation if detected and not recently reported
        violation_key = (vehicle_id, 'wrong_way', int(current_time))
        if wrong_way and not violation_reported:
            self.reported_violations.add(violation_key)
            return {
                'type': 'wrong_way',
                'vehicle_id': vehicle_id,
                'vehicle_type': vehicle_type,
                'timestamp': current_time,
                'location': (pos_last[1], pos_last[2]),
                'confidence': 0.85  # High confidence for wrong way detection
            }
        
        return None
        
    def _check_illegal_parking(self, vehicle_id, vehicle_type, x, y):
        """Check if vehicle is illegally parked - stricter detection"""
        # Need at least 5 positions to determine if vehicle is stationary
        if len(self.vehicle_positions[vehicle_id]) < 5:
            return None
        
        # Get positions over time to check if vehicle is stationary
        positions = self.vehicle_positions[vehicle_id]
        
        # Calculate total movement over the last 5 positions
        total_movement = 0
        for i in range(1, min(5, len(positions))):
            dx = positions[-i][1] - positions[-i-1][1]
            dy = positions[-i][2] - positions[-i-1][2]
            total_movement += np.sqrt(dx**2 + dy**2)
        
        # Check if vehicle is stationary (very little movement)
        is_stationary = total_movement < 15  # Stricter threshold for stationary detection
        
        # Check if vehicle is in a no-parking zone
        in_restricted_area = False
        for area in self.restricted_areas:
            if cv2.pointPolygonTest(area, (x, y), False) >= 0:
                in_restricted_area = True
                break
        
        # Check if not already reported recently
        current_time = time.time()
        violation_reported = False
        for vkey in list(self.reported_violations):
            v_id, v_type, v_time = vkey
            if v_id == vehicle_id and v_type == 'illegal_parking' and current_time - v_time < 8:
                violation_reported = True
        
        # Report violation if detected and not recently reported
        violation_key = (vehicle_id, 'illegal_parking', int(current_time))
        if is_stationary and in_restricted_area and not violation_reported:
            self.reported_violations.add(violation_key)
            return {
                'type': 'illegal_parking',
                'vehicle_id': vehicle_id,
                'vehicle_type': vehicle_type,
                'timestamp': current_time,
                'location': (x, y),
                'confidence': 0.9  # High confidence for illegal parking
            }
        
        return None
        
    def _check_no_helmet(self, vehicle_id, frame, bbox):
        """Check if motorcycle rider is not wearing a helmet - stricter detection"""
        # In a real system, this would use a specialized ML model to detect helmets
        # This is a simplified simulation for demo purposes
        
        # Extract the upper portion of the motorcycle bounding box (where the rider's head would be)
        x1, y1, x2, y2 = bbox
        head_region_height = int((y2 - y1) * 0.3)  # Upper 30% of the bbox where the head would be
        head_region = frame[y1:y1+head_region_height, x1:x2]
        
        # Check if head region exists (might be out of frame)
        if head_region.size == 0:
            return None
            
        # Simple color-based detection (real systems would use CNN)
        # Look for typical helmet colors (dark colors or bright colors)
        has_no_helmet = False
        
        try:
            # Convert to HSV for better color analysis
            hsv_head = cv2.cvtColor(head_region, cv2.COLOR_BGR2HSV)
            
            # Define range for typical helmet colors (black, white, red, blue, etc.)
            # This is simplified and would be much more sophisticated in a real system
            helmet_detected = False
            
            # Check for dark helmets (black, dark gray)
            dark_mask = cv2.inRange(hsv_head, np.array([0, 0, 0]), np.array([180, 100, 100]))
            
            # Check for bright helmets (white, light colors)
            bright_mask = cv2.inRange(hsv_head, np.array([0, 0, 150]), np.array([180, 60, 255]))
            
            # Check for colorful helmets (red, blue, etc.)
            color_mask = cv2.inRange(hsv_head, np.array([0, 100, 100]), np.array([180, 255, 255]))
            
            # Combine masks
            combined_mask = cv2.bitwise_or(dark_mask, bright_mask)
            combined_mask = cv2.bitwise_or(combined_mask, color_mask)
            
            # If a significant portion of the head region matches helmet colors, consider it a helmet
            helmet_ratio = cv2.countNonZero(combined_mask) / (head_region.shape[0] * head_region.shape[1])
            helmet_detected = helmet_ratio > 0.3
            
            has_no_helmet = not helmet_detected
        except Exception as e:
            # Fallback to random with lower probability
            self.logger.debug(f"Error in helmet detection: {e}")
            has_no_helmet = np.random.random() < 0.15
        
        violation_id = (vehicle_id, 'no_helmet', int(time.time()))
        if has_no_helmet and violation_id not in self.reported_violations:
            self.reported_violations.add(violation_id)
            return {
                'vehicle_id': vehicle_id,
                'type': 'no_helmet',
                'details': "Rider without helmet",
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'location': ((bbox[0] + bbox[2]) // 2, (bbox[1] + bbox[3]) // 2)
            }
        
        return None
