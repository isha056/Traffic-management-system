import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

class CredentialsManager:
    def __init__(self, env_path: Optional[str] = None):
        """Initialize the credentials manager.
        
        Args:
            env_path: Path to the .env file (optional)
        """
        if env_path:
            load_dotenv(env_path)
        else:
            # Look for .env file in the project root
            default_env_path = Path(__file__).parent.parent / '.env'
            if default_env_path.exists():
                load_dotenv(default_env_path)
            else:
                load_dotenv()  # Try to load from current directory
    
    @staticmethod
    def get_google_api_key() -> Optional[str]:
        """Get the Google API key from environment variables."""
        return os.getenv('GOOGLE_API_KEY')
    
    @staticmethod
    def validate_google_api_key(api_key: Optional[str]) -> bool:
        """Validate the Google API key format.
        
        Args:
            api_key: The API key to validate
            
        Returns:
            bool: True if the API key is valid, False otherwise
        """
        if not api_key:
            return False
        # Basic validation - check if it matches expected format
        return len(api_key) > 20 and api_key.startswith('AIza')