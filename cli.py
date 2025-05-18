import argparse
import logging
from pathlib import Path
from typing import Optional

def setup_logging(level: str = 'INFO') -> None:
    """Setup logging configuration.
    
    Args:
        level: Logging level (default: INFO)
    """
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f'Invalid log level: {level}')
    
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('traffic_detection.log')
        ]
    )

def parse_args() -> argparse.Namespace:
    """Parse command line arguments.
    
    Returns:
        Parsed command line arguments
    """
    parser = argparse.ArgumentParser(
        description='Traffic Management System - Vehicle Detection and Tracking',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        '--video',
        type=str,
        required=True,
        help='Path to the input video file'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        help='Path to the configuration file (YAML)'
    )
    
    parser.add_argument(
        '--log-level',
        type=str,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='INFO',
        help='Set the logging level'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        help='Path to save output video/frames'
    )
    
    parser.add_argument(
        '--no-display',
        action='store_true',
        help='Disable display window'
    )
    
    return parser.parse_args()

def validate_paths(video_path: str, config_path: Optional[str] = None, output_path: Optional[str] = None) -> None:
    """Validate input and output paths.
    
    Args:
        video_path: Path to input video file
        config_path: Path to configuration file (optional)
        output_path: Path to output directory (optional)
    
    Raises:
        FileNotFoundError: If required files don't exist
        ValueError: If paths are invalid
    """
    # Validate video path
    video = Path(video_path)
    if not video.exists():
        raise FileNotFoundError(f'Video file not found: {video_path}')
    
    # Validate config path if provided
    if config_path:
        config = Path(config_path)
        if not config.exists():
            raise FileNotFoundError(f'Configuration file not found: {config_path}')
    
    # Validate output path if provided
    if output_path:
        output = Path(output_path)
        if output.exists() and not output.is_dir():
            raise ValueError(f'Output path exists but is not a directory: {output_path}')
        output.mkdir(parents=True, exist_ok=True)