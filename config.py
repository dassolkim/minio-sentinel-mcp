"""Configuration management for MinIO MCP Server."""

from pydantic_settings import BaseSettings
from pydantic import Field, field_validator, ConfigDict
from typing import Optional


class MinIOConfig(BaseSettings):
    """MinIO MCP Server configuration settings."""

    # Keycloak Configuration
    keycloak_server_url: str = Field(..., description="Keycloak server URL")
    keycloak_realm: str = Field(..., description="Keycloak realm")
    keycloak_client_id: str = Field(..., description="Keycloak client ID")
    keycloak_client_secret: str = Field(..., description="Keycloak client secret")
    keycloak_verify_ssl: bool = Field(True, description="Verify SSL for Keycloak")

    # MinIO API Configuration
    minio_api_base_url: str = Field(..., description="MinIO API base URL")
    minio_api_timeout: int = Field(30, description="MinIO API timeout in seconds")
    minio_secure: bool = Field(True, description="Use HTTPS for MinIO")
    minio_region: str = Field("us-east-1", description="MinIO default region")

    # MCP Server Configuration
    mcp_server_name: str = Field("MinIO MCP Server", description="MCP server name")
    mcp_server_version: str = Field("1.0.0", description="MCP server version")

    # Logging Configuration
    log_level: str = Field("INFO", description="Logging level")

    # Security Configuration
    jwt_algorithm: str = Field("RS256", description="JWT algorithm")
    token_cache_ttl: int = Field(3600, description="Token cache TTL in seconds")

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"  # 추가 필드 무시
    )

    @field_validator("keycloak_server_url", "minio_api_base_url")
    @classmethod
    def validate_urls(cls, v):
        """Validate that URLs are properly formatted."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v.rstrip("/")

    @field_validator("minio_api_timeout")
    @classmethod
    def validate_timeout(cls, v):
        """Validate timeout is reasonable."""
        if v < 1 or v > 300:
            raise ValueError("Timeout must be between 1 and 300 seconds")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v.upper()


# Global configuration instance (lazy initialization)
_config: MinIOConfig = None


def get_config() -> MinIOConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = MinIOConfig()
    return _config