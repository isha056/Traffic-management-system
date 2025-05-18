import logging
from pathlib import Path
from vehicle_detection.detector import VehicleDetectionProcessor
from cli import parse_args, setup_logging, validate_paths

def main():
    """Main entry point for the Traffic Management System."""
    # Parse command line arguments
    args = parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    try:
        # Validate input paths
        validate_paths(
            video_path=args.video,
            config_path=args.config,
            output_path=args.output
        )
        
        # Initialize detector with configuration
        detector = VehicleDetectionProcessor(
            video_path=args.video,
            config_path=args.config
        )
        
        # Update configuration based on command line arguments
        if args.no_display:
            detector.config.display_output = False
        if args.output:
            detector.config.save_output = True
            detector.config.output_path = args.output
        
        logger.info("Starting vehicle detection...")
        detector.start_processing()
        
        # Wait for user input to stop
        try:
            input('Press Enter to stop detection...')
        except KeyboardInterrupt:
            logger.info('Detection stopped by user')
        
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return 1
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1
    finally:
        if 'detector' in locals():
            detector.stop_processing()
            counts = detector.get_vehicle_counts()
            logger.info('\nFinal Vehicle Counts:')
            for vehicle_type, count in counts.items():
                logger.info(f'{vehicle_type}: {count}')
    
    return 0

if __name__ == '__main__':
    exit(main())