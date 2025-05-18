import cv2
import numpy as np
import cvzone

def process_frame(frame, result, area_coordinates):
    """Process a single frame with detection results."""
    # Draw bounding boxes and labels
    for box in result.boxes:
        # Get box coordinates
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        conf = float(box.conf[0])
        cls = int(box.cls[0])
        
        # Check if object is in the detection area
        center = ((x1 + x2) // 2, (y2 + y1) // 2)
        if cv2.pointPolygonTest(area_coordinates, center, False) >= 0:
            # Draw bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 255), 3)
            
            # Add label with confidence
            label = f'{result.names[cls]} {conf:.2f}'
            cvzone.putTextRect(frame, label, (max(0, x1), max(35, y1)),
                              scale=1, thickness=1)
    
    return frame

def draw_area(frame, area_coordinates):
    """Draw the detection area on the frame."""
    # Draw detection area
    cv2.polylines(frame, [area_coordinates], True, (0, 255, 0), 2)
    
    return frame

def calculate_center(box):
    """Calculate the center point of a bounding box."""
    x1, y1, x2, y2 = map(int, box.xyxy[0])
    return ((x1 + x2) // 2, (y2 + y1) // 2)

def calculate_fps(frame_time):
    """Calculate frames per second."""
    if frame_time > 0:
        return 1.0 / frame_time
    return 0.0