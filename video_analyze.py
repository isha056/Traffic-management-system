import cv2
import os
import sys
import numpy as np

def analyze_video(video_path):
    """Analyze video file and print key information."""
    if not os.path.exists(video_path):
        print(f"Error: Video file not found at {video_path}")
        return
    
    # Open the video file
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Could not open video {video_path}")
        return
    
    # Get video properties
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frame_count / fps if fps > 0 else 0
    
    print(f"Video Analysis for: {os.path.basename(video_path)}")
    print(f"Resolution: {width}x{height}")
    print(f"FPS: {fps:.2f}")
    print(f"Frame Count: {frame_count}")
    print(f"Duration: {duration:.2f} seconds ({duration/60:.2f} minutes)")
    
    # Analyze some frames
    frame_step = max(1, frame_count // 10)  # Analyze 10 frames distributed throughout the video
    
    # Variables for motion analysis
    frame_samples = []
    frame_diffs = []
    
    prev_frame = None
    
    for frame_idx in range(0, frame_count, frame_step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        
        if not ret:
            break
        
        # Convert to grayscale for motion analysis
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Store sample frame
        frame_samples.append(gray)
        
        # Calculate frame difference if we have a previous frame
        if prev_frame is not None:
            frame_diff = cv2.absdiff(prev_frame, gray)
            mean_diff = np.mean(frame_diff)
            frame_diffs.append(mean_diff)
        
        prev_frame = gray
    
    # Print motion analysis
    if frame_diffs:
        avg_motion = np.mean(frame_diffs)
        print(f"Average Motion (pixel difference): {avg_motion:.2f}")
        
        if avg_motion < 5:
            print("Video has very low motion - mostly static scenes")
        elif avg_motion < 15:
            print("Video has moderate motion - slow-moving traffic or surveillance")
        else:
            print("Video has high motion - fast-moving traffic or camera movement")
    
    # Check for potential traffic directions
    print("\nAnalyzing video for traffic patterns...")
    
    # Sample a few more frames for this specific analysis
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    
    # Calculate optical flow on a few frames
    prev_gray = None
    flow_directions = []
    
    for i in range(min(30, frame_count - 1)):
        ret, frame = cap.read()
        if not ret:
            break
            
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        if prev_gray is not None:
            # Calculate optical flow using Lucas-Kanade method
            try:
                flow = cv2.calcOpticalFlowFarneback(prev_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
                
                # Get mean flow direction
                if flow is not None and flow.size > 0:
                    mean_x = np.mean(flow[..., 0])
                    mean_y = np.mean(flow[..., 1])
                    flow_directions.append((mean_x, mean_y))
            except Exception as e:
                print(f"Error calculating optical flow: {e}")
        
        prev_gray = gray
    
    # Analyze flow directions
    if flow_directions:
        mean_x = np.mean([d[0] for d in flow_directions])
        mean_y = np.mean([d[1] for d in flow_directions])
        
        dominant_x = "right" if mean_x > 0 else "left"
        dominant_y = "down" if mean_y > 0 else "up"
        
        # Determine which direction is stronger
        if abs(mean_x) > abs(mean_y):
            print(f"Dominant traffic direction appears to be horizontal ({dominant_x})")
            if abs(mean_x) > 2 * abs(mean_y):
                print("Traffic is primarily moving horizontally")
            else:
                print("Traffic has significant horizontal and vertical components")
        else:
            print(f"Dominant traffic direction appears to be vertical ({dominant_y})")
            if abs(mean_y) > 2 * abs(mean_x):
                print("Traffic is primarily moving vertically")
            else:
                print("Traffic has significant horizontal and vertical components")
    
    # Detect potential traffic light locations
    print("\nChecking for potential traffic light regions...")
    
    # Sample a frame from the middle of the video
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_count // 2)
    ret, frame = cap.read()
    
    if ret:
        # Convert to HSV for better color detection
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Define range for red color (typical for traffic lights)
        lower_red1 = np.array([0, 120, 70])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([170, 120, 70])
        upper_red2 = np.array([180, 255, 255])
        
        # Create masks
        mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
        red_mask = cv2.bitwise_or(mask1, mask2)
        
        # Find contours
        contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if contours:
            print(f"Found {len(contours)} potential red regions - some might be traffic lights")
            
            # Filter by size to find traffic light candidates
            traffic_light_candidates = []
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                area = w * h
                
                # Traffic lights typically have a small to medium size and are taller than wide
                if 100 < area < 5000 and h > w:
                    traffic_light_candidates.append((x, y, w, h))
            
            if traffic_light_candidates:
                print(f"Found {len(traffic_light_candidates)} traffic light candidates")
                for i, (x, y, w, h) in enumerate(traffic_light_candidates[:3]):  # Show top 3
                    print(f"  Candidate {i+1}: at ({x}, {y}) with size {w}x{h}")
            else:
                print("No strong traffic light candidates found")
        else:
            print("No red regions found - likely no visible traffic lights")
    
    cap.release()
    
    print("\nSuggestions for violation detector configuration:")
    print("1. Set wrong_way_direction based on the dominant traffic flow")
    if 'dominant_x' in locals() and 'dominant_y' in locals():
        if abs(mean_x) > abs(mean_y):
            suggested_direction = "east" if mean_x < 0 else "west"
        else:
            suggested_direction = "north" if mean_y < 0 else "south"
        print(f"   Suggested value: '{suggested_direction}'")
    
    print("2. Define reasonable restricted areas (no-parking zones)")
    print(f"   Suggested starting point: np.array([(100, 100), (100, {height-100}), ({width-100}, {height-100}), ({width-100}, 100)], np.int32)")
    
    if 'traffic_light_candidates' in locals() and traffic_light_candidates:
        # Use the first candidate to suggest a line
        x, y, w, h = traffic_light_candidates[0]
        line_y = y + h
        line_x1 = max(0, x - 50)
        line_x2 = min(width, x + w + 50)
        print("3. Set red light coordinates near detected traffic light")
        print(f"   Suggested value: [({line_x1}, {line_y}), ({line_x2}, {line_y})]")
    else:
        print("3. Set red light coordinates at a logical intersection")
        print(f"   Suggested value: [({width//4}, {height//2}), ({3*width//4}, {height//2})]")
    
    print("4. Calibrate speed threshold based on the video context")
    if 'avg_motion' in locals():
        if avg_motion < 10:
            suggested_speed = 30  # Slower for low motion videos
        elif avg_motion < 20:
            suggested_speed = 50  # Medium for moderate motion
        else:
            suggested_speed = 70  # Higher for high motion
        print(f"   Suggested value: {suggested_speed} km/h")
    else:
        print("   Suggested value: 50 km/h")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        video_path = sys.argv[1]
    else:
        video_path = "Traffic-Management-System/my.mp4"
    
    analyze_video(video_path)
