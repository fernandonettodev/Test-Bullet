from pydantic_settings import BaseSettings
from typing import List
from functools import lru_cache


class Settings(BaseSettings):
    # Application settings
    app_name: str = "Transaction Processing API"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Logging settings
    log_level: str = "INFO"
    log_format: str = "json"  # json or text
    
    # Security settings
    rate_limit_per_minute: int = 30
    max_request_size: int = 1024 * 1024  # 1MB
    
    # CORS settings
    allowed_origins: List[str] = ["*"]  # In production, specify exact origins
    allowed_methods: List[str] = ["GET", "POST", "OPTIONS"]
    allowed_headers: List[str] = ["*"]
    
    # Business logic settings
    max_transaction_amount: float = 1000000.00  # $1M limit
    min_transaction_amount: float = 0.01  # $0.01 minimum
    
    # Timezone
    timezone: str = "America/Sao_Paulo"
    
    # Feature flags
    enable_metrics: bool = True
    enable_detailed_logging: bool = True
    enable_request_validation: bool = True
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        
        # Environment variable mapping
        fields = {
            "app_name": {"env": "APP_NAME"},
            "debug": {"env": "DEBUG"},
            "log_level": {"env": "LOG_LEVEL"},
            "rate_limit_per_minute": {"env": "RATE_LIMIT_PER_MINUTE"},
            "allowed_origins": {"env": "ALLOWED_ORIGINS"},
            "max_transaction_amount": {"env": "MAX_TRANSACTION_AMOUNT"},
            "min_transaction_amount": {"env": "MIN_TRANSACTION_AMOUNT"},
            "timezone": {"env": "TIMEZONE"},
        }


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Environment-specific configurations
class DevelopmentSettings(Settings):
    debug: bool = True
    log_level: str = "DEBUG"
    enable_detailed_logging: bool = True
    rate_limit_per_minute: int = 100  # More lenient for development


class ProductionSettings(Settings):
    debug: bool = False
    log_level: str = "INFO"
    allowed_origins: List[str] = []  # Must be specified in production
    enable_detailed_logging: bool = False
    rate_limit_per_minute: int = 30


class TestingSettings(Settings):
    debug: bool = True
    log_level: str = "WARNING"  # Reduce noise in tests
    rate_limit_per_minute: int = 1000  # No rate limiting in tests
    enable_metrics: bool = False


def get_settings_for_environment(env: str = "development") -> Settings:
    """Get settings for specific environment."""
    settings_map = {
        "development": DevelopmentSettings,
        "production": ProductionSettings,
        "testing": TestingSettings,
    }
    
    settings_class = settings_map.get(env.lower(), Settings)
    return settings_class()