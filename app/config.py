"""
Configuration settings for the FastAPI application
"""
from pydantic_settings import BaseSettings
import json
from typing import Dict, Any


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    firebase_service_account_key: str
    
    environment: str = "development"
    debug: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"
    
    def get_firebase_credentials(self) -> Dict[str, Any]:
        """Parse Firebase service account key from JSON string"""
        try:
            print("📋 Loading Firebase service account key from environment...")
            credentials = json.loads(self.firebase_service_account_key)
            print(f"📋 Environment variable loaded successfully")
            return credentials
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse Firebase service account key: {e}")
            raise ValueError(f"Invalid Firebase service account key JSON: {e}")


settings = Settings()