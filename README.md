# AI-Driven Traffic Management System

![Traffic Management](https://img.shields.io/badge/AI-Traffic%20Management-blue)
![Python](https://img.shields.io/badge/Python-3.8%2B-brightgreen)
![Flask](https://img.shields.io/badge/Flask-2.0%2B-red)
![YOLOv8](https://img.shields.io/badge/YOLOv8-Latest-yellow)

An advanced AI-powered system for traffic monitoring and violation detection with a web-based interface.

## Features

- **Real-time Vehicle Detection**: Detect and track multiple vehicle types in video feeds
- **Traffic Violation Detection**: Automatically identify various traffic violations:
  - Speeding
  - Red Light Violations
  - Wrong Way Driving
  - Illegal Parking
  - No Helmet (for motorcyclists)
- **Web Interface**: User-friendly dashboard with real-time monitoring capabilities
- **Analytics**: Generate insights and statistics on traffic patterns and violations
- **Database Integration**: Store detection and violation data for analysis

## System Architecture

The system consists of the following components:

1. **Detection Module**: Uses YOLOv8 for vehicle detection and tracking
2. **Violation Detector**: Analyzes vehicle behavior to identify traffic violations
3. **Database Handler**: Stores detection and violation data using SQLite
4. **Web Interface**: Flask-based web application with real-time updates via WebSockets

## Installation

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Virtual environment (recommended)

### Setup

1. Clone the repository:
   ```
   git clone https://github.com/username/Traffic-Management-System.git
   cd Traffic-Management-System
   ```

2. Create and activate a virtual environment (optional but recommended):
   ```
   python -m venv venv
   # On Windows
   venv\Scripts\activate
   # On macOS/Linux
   source venv/bin/activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   - Create a `.env` file based on the provided `.env.example`
   - Add your Google API key (if using Google API features)

## Usage

### Command-Line Interface

Run the system via command line:

```
python main.py --video "path/to/video/file.mp4"
```

Additional options:
- `--config`: Path to configuration file (YAML)
- `--output`: Path to save output video/frames
- `--no-display`: Disable GUI display
- `--log-level`: Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

### Web Interface

Start the web application:

```
python web_app/app.py
```

Then navigate to `http://localhost:5000` in your web browser.

The web interface includes:

- **Dashboard**: Real-time monitoring with vehicle counts and violation statistics
- **Violations**: Detailed log of all detected violations with filtering options
- **Settings**: Configure detection parameters and system settings

## Configuration

The system can be configured through the web interface or by editing the YAML configuration file. Key settings include:

- **Model settings**: YOLOv8 model path, confidence threshold, NMS threshold
- **Video processing**: Frame skip, display options, output settings
- **Detection area**: Define specific zones for monitoring
- **Violation thresholds**: Speed limits, red light zones, etc.

## API Endpoints

The web application provides the following API endpoints:

- `GET /api/vehicle_counts`: Get current vehicle counts
- `GET /api/violations`: Get current violation statistics
- `POST /start_processing`: Start video processing
- `POST /stop_processing`: Stop video processing

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- [Ultralytics](https://github.com/ultralytics/ultralytics) for YOLOv8
- [OpenCV](https://opencv.org/) for computer vision capabilities
- [Flask](https://flask.palletsprojects.com/) for the web framework
- [Socket.IO](https://socket.io/) for real-time communication