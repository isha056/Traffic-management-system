import os
import cv2
import time
import base64
import threading
import logging
import os
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, Response, request, jsonify, redirect, url_for
from flask_socketio import SocketIO
from PIL import Image
import io
import sys
import traceback

# Add parent directory to the path so we can import from vehicle_detection
parent_dir = str(Path(__file__).parent.parent.absolute())
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Set up proper working directory relative paths
ROOT_DIR = Path(__file__).parent.parent.absolute()

from vehicle_detection.detector import VehicleDetectionProcessor
from vehicle_detection.database import DatabaseHandler
from vehicle_detection.utils import draw_area
from vehicle_detection.config import DetectionConfig
from vehicle_detection.violation_detector import ViolationDetector

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'traffic_system_secret_key'
socketio = SocketIO(app)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(ROOT_DIR, 'web_app_debug.log'))
    ]
)
logger = logging.getLogger(__name__)
logger.info(f"Application starting. Root directory: {ROOT_DIR}")

# Global variables
detector = None
frame_queue = []
latest_frame = None
latest_vehicle_counts = {}
latest_violations = []
processing_active = False
config_path = None
video_path = None
output_path = None

# Current violations - will be updated by ViolationDetector
current_violations = {
    'speeding': 0,
    'red_light': 0,
    'wrong_way': 0,
    'illegal_parking': 0,
    'no_helmet': 0,
    'unauthorized_person': 0
}


def get_base64_image(frame):
    """Convert OpenCV frame to base64 encoded string for web display"""
    if frame is None:
        logger.warning("Cannot encode None frame")
        return None
    
    try:
        # Ensure frame is properly formatted for encoding
        if frame.ndim == 2:  # Grayscale
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        
        # Resize frame to reduce bandwidth usage
        frame = cv2.resize(frame, (800, 450))
        
        # Compress image with lower quality for faster transmission
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 80]
        success, buffer = cv2.imencode('.jpg', frame, encode_param)
        
        if not success:
            logger.error("Failed to encode frame to JPEG")
            return None
        
        jpg_as_text = base64.b64encode(buffer).decode('utf-8')
        return jpg_as_text
    except Exception as e:
        logger.error(f"Error encoding frame: {e}")
        return None


def process_frame_for_web(frame, vehicle_counts, violations):
    """Process a frame for web display with overlays"""
    if frame is None:
        return None
    
    # Draw vehicle counts
    y_offset = 30
    for vehicle_type, count in vehicle_counts.items():
        text = f"{vehicle_type}: {count}"
        cv2.putText(frame, text, (20, y_offset), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        y_offset += 30
    
    # Draw violation information
    for i, violation in enumerate(violations[-5:]):  # Show only the 5 most recent violations
        text = f"{violation['type']}: {violation['details']}"
        cv2.putText(frame, text, (20, frame.shape[0] - 30 - (i * 30)), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    
    return frame


class FrameProcessor:
    def __init__(self, video_path, config_path=None):
        # Handle numeric video sources (e.g., '0' for webcam)
        if isinstance(video_path, str) and video_path.isdigit():
            self.video_source = int(video_path)
        else:
            # Make sure file paths are absolute
            path = video_path
            if not os.path.isabs(path):
                path = os.path.join(ROOT_DIR, path)
            self.video_source = path
        # Config path handling
        if config_path:
            self.config_path = config_path if os.path.isabs(config_path) else os.path.join(ROOT_DIR, config_path)
        else:
            self.config_path = None
         
        logger.info(f"Initializing FrameProcessor with video: {self.video_source}")
        
        # Check if video exists
        if isinstance(self.video_source, str) and not os.path.exists(self.video_source):
            logger.error(f"Video file not found: {self.video_source}")
            # Try to find the video in some common locations
            potential_paths = [
                os.path.join(ROOT_DIR, 'my.mp4'),
                os.path.join(ROOT_DIR, 'Traffic-Management-System', 'my.mp4'),
                os.path.join(os.path.dirname(ROOT_DIR), 'my.mp4'),
                os.path.join(os.path.dirname(os.path.dirname(ROOT_DIR)), 'my.mp4')
            ]
            
            # Also try relative to the current working directory
            cwd_path = os.path.join(os.getcwd(), 'my.mp4')
            if os.path.exists(cwd_path):
                logger.info(f"Found video in current working directory: {cwd_path}")
                self.video_source = cwd_path
            else:
                for path in potential_paths:
                    if os.path.exists(path):
                        logger.info(f"Found video at alternate location: {path}")
                        self.video_source = path
                        break
                else:
                    logger.warning(f"No video file found in known locations. Falling back to webcam (device 0).")
                    self.video_source = 0  # Fallback to webcam
        
        self.detector = None
        self.violation_detector = None
        self.is_processing = False
        self.thread = None
        
    def start(self):
        if self.is_processing:
            return False
        
        try:
            # For file sources, check existence
            if isinstance(self.video_source, str) and not os.path.exists(self.video_source):
                error_msg = f"Video file not found: {self.video_source}"
                logger.error(error_msg)
                return False, error_msg
            
            # Log detailed information about the video file
            if isinstance(self.video_source, str):
                logger.info(f"Video file path: {self.video_source}")
                logger.info(f"Video file exists: {os.path.exists(self.video_source)}")
                logger.info(f"Video file is absolute: {os.path.isabs(self.video_source)}")
                logger.info(f"Current working directory: {os.getcwd()}")
                logger.info(f"ROOT_DIR: {ROOT_DIR}")
            
            # Initialize detector
            logger.info(f"Creating VehicleDetectionProcessor with {self.video_source}")
            self.detector = VehicleDetectionProcessor(self.video_source, self.config_path)
            
            # Initialize violation detector
            logger.info("Creating ViolationDetector")
            self.violation_detector = ViolationDetector(self.detector)
            
            # Start processing
            self.is_processing = True
            self.thread = threading.Thread(target=self._process_frames)
            self.thread.daemon = True
            self.thread.start()
            logger.info("Processing started successfully")
            return True
        except Exception as e:
            error_msg = f"Error starting frame processor: {e}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            return False
    
    def stop(self):
        self.is_processing = False
        if self.detector:
            self.detector.stop_processing()
        if self.thread:
            self.thread.join(timeout=2.0)
    
    def _process_frames(self):
        global latest_frame, latest_vehicle_counts, latest_violations, current_violations
        
        try:
            logger.info(f"Opening video capture for: {self.video_source}")
            cap = cv2.VideoCapture(self.video_source)
            if not cap.isOpened():
                logger.error(f"Failed to open video: {self.video_source}")
                
                # Try with different backend
                logger.info("Attempting with different backend...")
                cap = cv2.VideoCapture(self.video_source, cv2.CAP_FFMPEG)
                if not cap.isOpened():
                    logger.error("All attempts to open video failed")
                    self.is_processing = False
                    return
                else:
                    logger.info("Successfully opened video with FFMPEG backend")
            
            frame_count = 0
            
            while self.is_processing:
                success, frame = cap.read()
                if not success:
                    # If video ends, loop back to the beginning
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                
                frame_count += 1
                
                # Process frame with detector
                # We're using our own processing logic here instead of detector.start_processing()
                # to have more control over the real-time display
                try:
                    # Apply YOLO detection
                    results = self.detector.model.track(
                        frame, 
                        persist=True,
                        conf=self.detector.config.confidence_threshold,
                        iou=self.detector.config.nms_threshold
                    )
                    
                    if results and len(results) > 0 and hasattr(results[0].boxes, 'id') and results[0].boxes.id is not None:
                        # Update vehicle counts
                        self.detector._update_vehicle_data(results[0])
                        latest_vehicle_counts = self.detector.get_vehicle_counts()
                        
                        # Process for violations
                        new_violations = self.violation_detector.detect_violations(frame, results[0])
                        if new_violations:
                            latest_violations.extend(new_violations)
                            # Update violation counts
                            for violation in new_violations:
                                v_type = violation['type']
                                if v_type in current_violations:
                                    current_violations[v_type] += 1
                        
                        # Draw area on frame
                        processed_frame = draw_area(frame.copy(), self.detector.area_coordinates)
                        
                        # Process frame for web display
                        web_frame = process_frame_for_web(
                            processed_frame,
                            latest_vehicle_counts,
                            latest_violations
                        )
                        
                        # Update latest frame
                        latest_frame = web_frame
                        
                        # Emit frame to websocket
                        if frame_count % 3 == 0:  # only emit every 3rd frame to reduce load
                            frame_b64 = get_base64_image(web_frame)
                            if frame_b64:
                                logger.debug(f"Emitting frame {frame_count} to clients")
                                try:
                                    socketio.emit('frame_update', {
                                        'frame': frame_b64,
                                        'vehicle_counts': latest_vehicle_counts,
                                        'violations': current_violations
                                    })
                                except Exception as e:
                                    logger.error(f"Error emitting frame: {e}")
                    
                    # Control frame rate
                    time.sleep(0.03)  # ~30 FPS max
                
                except Exception as e:
                    logger.error(f"Error processing frame {frame_count}: {e}")
                    time.sleep(0.1)  # Add delay on error
            
        except Exception as e:
            logger.error(f"Error in frame processing loop: {e}")
        finally:
            if cap:
                cap.release()


@app.route('/')
def index():
    """Home page"""
    return render_template('index.html')


@app.route('/dashboard')
def dashboard():
    db_handler = DatabaseHandler('traffic.db')
    daily_counts = db_handler.get_daily_counts()
    return render_template('dashboard.html', vehicle_counts=daily_counts)


@app.route('/violations')
def violations():
    """Violations log page"""
    return render_template('violations.html', violations=latest_violations)


@app.route('/settings')
def settings():
    """Settings page"""
    return render_template('settings.html')


@app.route('/start_processing', methods=['POST'])
def start_processing():
    """Start processing a video"""
    global detector, processing_active, video_path, config_path
    
    if processing_active:
        return jsonify({'status': 'error', 'message': 'Processing already active'})
    
    data = request.form
    # Get video path with proper default
    default_video = os.path.join('my.mp4')
    video_path = data.get('video_path', default_video)
    logger.info(f"Requested video path: {video_path}")
    
    # Get config path
    config_path = data.get('config_path', None)
    
    try:
        # Create frame processor
        detector = FrameProcessor(video_path, config_path)
        result = detector.start()
        
        if result is True:
            processing_active = True
            return jsonify({'status': 'success', 'message': 'Processing started successfully'})
        else:
            error_message = "Failed to start processing"
            if isinstance(result, tuple) and len(result) > 1:
                error_message = result[1]
            return jsonify({'status': 'error', 'message': error_message})
    except Exception as e:
        error_message = f"Error starting processing: {e}"
        logger.error(error_message)
        logger.error(traceback.format_exc())
        return jsonify({'status': 'error', 'message': error_message})


@app.route('/stop_processing', methods=['POST'])
def stop_processing():
    """Stop video processing"""
    global detector, processing_active
    
    if not processing_active:
        return jsonify({'status': 'error', 'message': 'No active processing'})
    
    try:
        if detector:
            detector.stop()
        processing_active = False
        return jsonify({'status': 'success', 'message': 'Processing stopped'})
    except Exception as e:
        logger.error(f"Error stopping processing: {e}")
        return jsonify({'status': 'error', 'message': str(e)})


@app.route('/api/vehicle_counts')
def get_vehicle_counts():
    """API endpoint to get current vehicle counts"""
    return jsonify(latest_vehicle_counts)


@app.route('/api/violations')
def get_violations():
    """API endpoint to get current violations"""
    return jsonify({
        'total': sum(current_violations.values()),
        'counts': current_violations,
        'recent': latest_violations[-10:] if latest_violations else []
    })


@socketio.on('connect')
def handle_connect():
    """Handle websocket connection"""
    logger.info('Client connected')


@socketio.on('disconnect')
def handle_disconnect():
    """Handle websocket disconnection"""
    logger.info('Client disconnected')


if __name__ == '__main__':
    # Run the app - using localhost for Windows compatibility
    logger.info("Starting web server on http://localhost:5000")
    try:
        socketio.run(app, host='127.0.0.1', port=5000, debug=True, allow_unsafe_werkzeug=True)
    except Exception as e:
        logger.error(f"Error starting web server: {e}")
        # Try alternative method for older Flask versions
        try:
            logger.info("Trying alternative method to start server...")
            app.run(host='127.0.0.1', port=5000, debug=True)
        except Exception as e2:
            logger.error(f"Failed to start server with alternative method: {e2}")
