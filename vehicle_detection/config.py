from dataclasses import dataclass
from typing import List, Tuple, Optional
import yaml
import os
from .credentials import CredentialsManager

@dataclass
class DetectionConfig:
    # Model settings
    model_path: str = 'yolov8n.pt'
    confidence_threshold: float = 0.5
    nms_threshold: float = 0.45
    
    # Video processing
    frame_skip: int = 0  # Process every nth frame (0 means process all frames)
    display_output: bool = True
    save_output: bool = False
    output_path: Optional[str] = None
    
    # Detection area (can be overridden)
    default_area: List[Tuple[int, int]] = None
    
    # Database settings
    database_path: str = 'vehicle_detection.db'
    
    # API settings
    google_api_key: Optional[str] = None
    
    def __post_init__(self):
        if self.default_area is None:
            # Using a combined ROI that covers both lanes
            # Assuming 1920x1080 as base resolution
            w, h = 1920, 1080
            
            # Define a wider area that covers both lanes
            self.default_area = [
                (int(w*0.1), h),         # bottom left
                (int(w*0.9), h),         # bottom right
                (int(w*0.9), int(h*0.4)), # top right
                (int(w*0.1), int(h*0.4))  # top left
            ]
        
        # Load API key from environment
        credentials = CredentialsManager()
        self.google_api_key = credentials.get_google_api_key()
        
        if not credentials.validate_google_api_key(self.google_api_key):
            raise ValueError("Invalid or missing Google API key. Please set GOOGLE_API_KEY in your environment variables.")

    @classmethod
    def from_yaml(cls, config_path: str) -> 'DetectionConfig':
        """Load configuration from YAML file."""
        if not os.path.exists(config_path):
            return cls()
        
        with open(config_path, 'r') as f:
            config_dict = yaml.safe_load(f)
            return cls(**config_dict)
    
    def save_yaml(self, config_path: str) -> None:
        """Save configuration to YAML file."""
        config_dict = {
            'model_path': self.model_path,
            'confidence_threshold': self.confidence_threshold,
            'nms_threshold': self.nms_threshold,
            'frame_skip': self.frame_skip,
            'display_output': self.display_output,
            'save_output': self.save_output,
            'output_path': self.output_path,
            'default_area': self.default_area,
            'database_path': self.database_path
        }
        
        with open(config_path, 'w') as f:
            yaml.dump(config_dict, f, default_flow_style=False)