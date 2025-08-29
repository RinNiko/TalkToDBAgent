"""
Configuration management for the Talk to DB application.
All default values are defined here, not in .env files.
"""
import os
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with defaults defined here."""
    
    # Application Configuration
    app_env: str = Field(default="development", env="APP_ENV")
    app_port: int = Field(default=8000, env="APP_PORT")
    app_host: str = Field(default="0.0.0.0", env="APP_HOST")
    app_debug: bool = Field(default=True, env="APP_DEBUG")
    
    # CORS Configuration
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        env="CORS_ORIGINS"
    )
    
    # Security
    secret_key: str = Field(
        default="dev-secret-key-change-in-production-32-chars",
        env="SECRET_KEY"
    )
    encryption_secret: str = Field(
        default="dev-encryption-key-32-bytes-base64-encoded",
        env="ENCRYPTION_SECRET"
    )
    access_token_expire_minutes: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    
    # Database Configuration
    app_database_url: str = Field(
        default="sqlite:///./app.db",
        env="APP_DATABASE_URL"
    )
    
    # LLM Provider API Keys (defaults from environment, but not hardcoded)
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    openai_base_url: Optional[str] = Field(default=None, env="OPENAI_BASE_URL")
    azure_openai_api_key: Optional[str] = Field(default=None, env="AZURE_OPENAI_API_KEY")
    azure_openai_endpoint: Optional[str] = Field(default=None, env="AZURE_OPENAI_ENDPOINT")
    azure_openai_api_version: str = Field(
        default="2024-02-15-preview",
        env="AZURE_OPENAI_API_VERSION"
    )
    anthropic_api_key: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    gemini_api_key: Optional[str] = Field(default=None, env="GEMINI_API_KEY")
    groq_api_key: Optional[str] = Field(default=None, env="GROQ_API_KEY")
    
    # Rate Limiting
    rate_limit_per_minute: int = Field(default=60, env="RATE_LIMIT_PER_MINUTE")
    rate_limit_per_hour: int = Field(default=1000, env="RATE_LIMIT_PER_HOUR")
    
    # SQL Execution Settings
    max_execution_time_seconds: int = Field(default=300, env="MAX_EXECUTION_TIME_SECONDS")
    max_rows_returned: int = Field(default=10000, env="MAX_ROWS_RETURNED")
    require_sql_approval: bool = Field(default=False, env="REQUIRE_SQL_APPROVAL")
    read_only_mode: bool = Field(default=True, env="READ_ONLY_MODE")
    
    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(default="json", env="LOG_FORMAT")
    
    @field_validator("cors_origins", mode="before")
    def parse_cors_origins(cls, v):
        """Parse CORS origins from comma-separated string."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @field_validator("encryption_secret")
    def validate_encryption_secret(cls, v):
        """Validate encryption secret length."""
        if len(v) < 32:
            raise ValueError("Encryption secret must be at least 32 characters long")
        return v
    
    @field_validator("secret_key")
    def validate_secret_key(cls, v):
        """Validate secret key length."""
        if len(v) < 32:
            raise ValueError("Secret key must be at least 32 characters long")
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get settings instance."""
    return settings
