from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    app_name: str = "FastAPI Replit App"
    debug: bool = True
    version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    
    # Database settings (if needed)
    database_url: Optional[str] = None
    
    class Config:
        env_file = ".env"

#settings = Settings()