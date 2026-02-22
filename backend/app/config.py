# =============================================================================
# FGA CRM - Configuration
# =============================================================================

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "FGA CRM"
    app_version: str = "1.0.0"
    app_env: str = "development"
    app_debug: bool = True
    app_secret_key: str = "change-this-in-production"

    # Database
    database_url: str = "postgresql+asyncpg://fga_crm:devpassword@db:5432/fga_crm"
    database_pool_size: int = 5
    database_pool_max_overflow: int = 10

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # JWT Authentication
    jwt_secret_key: str = "change-this-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # WebAuthn
    webauthn_rp_id: str = "localhost"
    webauthn_rp_name: str = "FGA CRM"
    webauthn_origin: str = "http://localhost:3300"

    # AI - Claude
    claude_api_key: str | None = None
    claude_model: str = "claude-sonnet-4-20250514"

    # AI - OpenAI
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o"

    # Email - OVH
    ovh_smtp_host: str = "ssl0.ovh.net"
    ovh_smtp_port: int = 465
    ovh_imap_host: str = "ssl0.ovh.net"
    ovh_imap_port: int = 993
    ovh_email_user: str | None = None
    ovh_email_password: str | None = None

    # LinkedIn
    linkedin_client_id: str | None = None
    linkedin_client_secret: str | None = None
    linkedin_redirect_uri: str = "http://localhost:8300/api/v1/integrations/linkedin/callback"

    # Startup Radar Integration
    startup_radar_api_url: str = "http://startup-radar-backend:8000/api/v1"
    startup_radar_api_key: str | None = None
    startup_radar_email: str | None = None
    startup_radar_password: str | None = None

    # MinIO (S3-compatible)
    minio_endpoint: str = "minio:9000"
    minio_root_user: str = "minioadmin"
    minio_root_password: str = "minioadmin"
    minio_bucket: str = "fga-crm-files"
    minio_secure: bool = False

    # Encryption (Fernet for sensitive fields)
    encryption_key: str | None = None

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
