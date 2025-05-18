import cv2
import numpy as np
from ultralytics import YOLO
import cvzone
import time
import threading
import logging
from pathlib import Path
from vehicle_detection.database import DatabaseHandler
from vehicle_detection.utils import process_frame, draw_area, calculate_fps
from vehicle_detection.config import DetectionConfig

class VehicleDetectionProcessor:
    def __init__(self, video_path, config_path=None):
        """Initialize the vehicle detection processor.
        
        Args:
            video_path: Path to the video file
            config_path: Path to the configuration file (optional)
        """
        # Setup logging
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        
        # Load configuration
        self.config = DetectionConfig.from_yaml(config_path) if config_path else DetectionConfig()
        
        # Initialize video capture
        self.video_path = video_path
        
        # Handle different video source types
        if isinstance(video_path, (str, Path)) and str(video_path).isdigit():
            # This is a camera index
            self.logger.info(f"Using camera with index: {video_path}")
            self.cap = cv2.VideoCapture(int(video_path))
        else:
            # This is a file path
            try:
                # Convert to Path object for better path handling
                if isinstance(video_path, str):
                    self.video_path = Path(video_path)
                
                # Check if file exists
                if not Path(self.video_path).exists():
                    # Try to find the file in the current directory
                    current_dir = Path.cwd()
                    potential_paths = [
                        current_dir / 'my.mp4',
                        current_dir.parent / 'my.mp4',
                        Path(video_path).absolute()
                    ]
                    
                    for path in potential_paths:
                        if path.exists():
                            self.logger.info(f"Found video at: {path}")
                            self.video_path = path
                            break
                    else:
                        raise FileNotFoundError(f"Video file not found: {video_path}")
                
                self.logger.info(f"Opening video file: {self.video_path}")
                self.cap = cv2.VideoCapture(str(self.video_path))
            except Exception as e:
                self.logger.error(f"Error setting up video capture: {e}")
                raise
        
        if not self.cap.isOpened():
            raise RuntimeError(f"Failed to open video source: {video_path}")
        
        # Initialize YOLO model
        try:
            self.model = YOLO(self.config.model_path)
            self.logger.info(f"Loaded YOLO model: {self.config.model_path}")
        except Exception as e:
            self.logger.error(f"Failed to load YOLO model: {e}")
            raise
        
        # Set detection area
        self.area_coordinates = np.array(self.config.default_area, np.int32)
        
        # Initialize database handler
        self.db = DatabaseHandler(self.config.database_path)
        
        # Initialize tracking variables
        self.vehicle_counts = {}
        self.vehicle_ids = set()
        self.last_detection_time = time.time()
        self.frame_count = 0
        
        # Processing flags
        self.is_processing = False
        self.processing_thread = None
        
        self.logger.info("Vehicle Detection Processor initialized successfully")

    def start_processing(self):
        """Start the vehicle detection processing in a separate thread."""
        if not self.is_processing:
            self.is_processing = True
            self.processing_thread = threading.Thread(target=self._process_video)
            self.processing_thread.start()

    def stop_processing(self):
        """Stop the vehicle detection processing."""
        self.is_processing = False
        if self.processing_thread:
            self.processing_thread.join()

    def _process_video(self):
        """Main video processing loop."""
        try:
            frame_time = time.time()
            while self.is_processing:
                # Skip frames if configured
                if self.config.frame_skip > 0:
                    for _ in range(self.config.frame_skip):
                        self.cap.read()
                
                success, frame = self.cap.read()
                if not success:
                    self.logger.info("End of video reached")
                    break
                
                self.frame_count += 1
                
                try:
                    # Process frame and get detections
                    results = self.model.track(frame, persist=True,
                                             conf=self.config.confidence_threshold,
                                             iou=self.config.nms_threshold)
                    
                    if results and results[0].boxes.id is not None:
                        # Process detections and update counts
                        processed_frame = process_frame(frame, results[0], self.area_coordinates)
                        
                        # Update vehicle counts and database
                        self._update_vehicle_data(results[0])
                        
                        # Draw detection area
                        processed_frame = draw_area(processed_frame, self.area_coordinates)
                        
                        # Calculate and display FPS
                        fps = calculate_fps(time.time() - frame_time)
                        cv2.putText(processed_frame, f'FPS: {fps:.1f}', (20, 30),
                                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                        
                        try:
                            # Only attempt to display if GUI is available
                            if self.config.display_output:
                                cv2.imshow('Vehicle Detection', processed_frame)
                                if cv2.waitKey(1) & 0xFF == ord('q'):
                                    self.logger.info("Processing stopped by user")
                                    break
                        except cv2.error:
                            self.logger.warning("GUI display not available")
                            # Continue processing without display
                            pass
                        
                        # Save output if enabled
                        if self.config.save_output and self.config.output_path:
                            output_path = Path(self.config.output_path)
                            output_path.parent.mkdir(parents=True, exist_ok=True)
                            cv2.imwrite(str(output_path / f'frame_{self.frame_count}.jpg'), processed_frame)
                    
                    frame_time = time.time()
                    
                except Exception as e:
                    self.logger.error(f"Error processing frame {self.frame_count}: {e}")
                    continue
        
        except Exception as e:
            self.logger.error(f"Error in video processing loop: {e}")
        finally:
            self.cap.release()
            try:
                cv2.destroyAllWindows()
            except cv2.error:
                self.logger.warning("Failed to destroy windows - GUI might not be available")
            self.logger.info("Video processing completed")

    def _update_vehicle_data(self, result):
        """Update vehicle detection data and database."""
        current_time = time.time()
        boxes = result.boxes
        for box in boxes:
            vehicle_id = int(box.id.item())
            if vehicle_id not in self.vehicle_ids:
                self.vehicle_ids.add(vehicle_id)
                class_id = int(box.cls.item())
                confidence = float(box.conf.item())
                
                # Update database
                self.db.insert_detection(
                    vehicle_id=vehicle_id,
                    class_id=class_id,
                    confidence=confidence,
                    timestamp=current_time
                )
                
                # Update counts
                vehicle_type = result.names[class_id]
                self.vehicle_counts[vehicle_type] = self.vehicle_counts.get(vehicle_type, 0) + 1

    def get_vehicle_counts(self):
        """Return the current vehicle counts."""
        return self.vehicle_counts

    def __del__(self):
        """Cleanup resources."""
        self.stop_processing()
        if hasattr(self, 'cap'):
            self.cap.release()
        cv2.destroyAllWindows()