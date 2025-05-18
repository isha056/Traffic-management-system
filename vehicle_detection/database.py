import sqlite3
from datetime import datetime
import threading
import logging

class DatabaseHandler:
    def __init__(self, db_path):
        """Initialize database connection and create tables if they don't exist."""
        self.db_path = db_path
        self.local = threading.local()
        self.logger = logging.getLogger(__name__)
        self.lock = threading.RLock()  # Add a lock for thread safety
        
        # Create tables in the main thread
        conn = self._get_connection()
        self._create_tables(conn)
        # Don't close the connection here as it might be needed later

    def _get_connection(self):
        """Get a thread-local database connection with proper locking."""
        with self.lock:
            if not hasattr(self.local, 'connection') or self.local.connection is None:
                try:
                    self.local.connection = sqlite3.connect(self.db_path, check_same_thread=False)
                    # Enable foreign keys
                    self.local.connection.execute('PRAGMA foreign_keys = ON')
                    # Set a longer timeout to avoid database locked errors
                    self.local.connection.execute('PRAGMA busy_timeout = 30000')
                    self.logger.debug(f"Created new database connection in thread {threading.get_ident()}")
                except sqlite3.Error as e:
                    self.logger.error(f"Database connection error: {e}")
                    raise
            return self.local.connection

    def _create_tables(self, connection):
        """Create necessary database tables if they don't exist."""
        try:
            cursor = connection.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vehicle_detections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vehicle_id INTEGER NOT NULL,
                    class_id INTEGER NOT NULL,
                    confidence REAL NOT NULL,
                    timestamp REAL NOT NULL,
                    detection_date TEXT NOT NULL
                )
            """)
            connection.commit()
        except sqlite3.Error as e:
            self.logger.error(f"Error creating tables: {e}")
            raise

    def insert_detection(self, vehicle_id, class_id, confidence, timestamp):
        """Insert a new vehicle detection record with proper error handling."""
        with self.lock:
            try:
                connection = self._get_connection()
                cursor = connection.cursor()
                detection_date = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
                cursor.execute("""
                    INSERT INTO vehicle_detections 
                    (vehicle_id, class_id, confidence, timestamp, detection_date)
                    VALUES (?, ?, ?, ?, ?)
                """, (vehicle_id, class_id, confidence, timestamp, detection_date))
                connection.commit()
            except sqlite3.Error as e:
                self.logger.error(f"Error inserting detection: {e}")
                # Try to reconnect if the database is closed
                if "closed database" in str(e).lower():
                    self.local.connection = None
                    self.logger.info("Attempting to reconnect to database")
                    return self.insert_detection(vehicle_id, class_id, confidence, timestamp)
                raise

    def get_daily_counts(self, date=None):
        """Get vehicle detection counts for a specific date with proper error handling."""
        with self.lock:
            try:
                if date is None:
                    date = datetime.now().strftime('%Y-%m-%d')
                
                connection = self._get_connection()
                cursor = connection.cursor()
                cursor.execute("""
                    SELECT class_id, COUNT(*) as count
                    FROM vehicle_detections
                    WHERE detection_date = ?
                    GROUP BY class_id
                """, (date,))
                return dict(cursor.fetchall())
            except sqlite3.Error as e:
                self.logger.error(f"Error getting daily counts: {e}")
                # Try to reconnect if the database is closed
                if "closed database" in str(e).lower():
                    self.local.connection = None
                    self.logger.info("Attempting to reconnect to database")
                    return self.get_daily_counts(date)
                raise

    def close_connection(self):
        """Explicitly close the database connection."""
        with self.lock:
            if hasattr(self.local, 'connection') and self.local.connection is not None:
                try:
                    self.local.connection.close()
                    self.logger.debug(f"Closed database connection in thread {threading.get_ident()}")
                except sqlite3.Error as e:
                    self.logger.error(f"Error closing database connection: {e}")
                finally:
                    self.local.connection = None
    
    def __del__(self):
        """Close database connection when object is destroyed."""
        try:
            self.close_connection()
        except Exception as e:
            # Just log the error, don't raise during garbage collection
            if self.logger:
                self.logger.error(f"Error in __del__: {e}")