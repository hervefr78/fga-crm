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
    auth_bypass: bool = False

    # CORS (origines supplémentaires, séparées par virgule)
    cors_origins: str | None = None

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

    # Nomo-IA Integration (incoming webhook from Marketing Assistant)
    nomo_api_key: str | None = None

    # Plein Phare Digital Integration (incoming webhook from plein-phare-api)
    plein_phare_api_key: str = ""

    # Compass-Core Integration (outgoing proxy — relecture des drafts)
    # URL racine du service compass-core (SANS /v1). Vide = proxy desactive (503).
    compass_api_url: str = ""
    # Cle service compass-core (Authorization: Bearer ...). Detenue cote serveur
    # uniquement, jamais exposee au navigateur. Vide = proxy desactive (503).
    compass_service_api_key: str = ""

    # MCP Usage — taux de conversion USD -> EUR pour le calcul du cout API.
    # Approximatif, a maintenir (cf. SHARED_ERRORS « prix LLM hardcode obsolete »).
    # Surchargeable via env EUR_USD.
    eur_usd: float = 0.92

    # GEO — Generative Engine Optimization
    perplexity_api_key: str | None = None
    gemini_api_key: str | None = None
    serpapi_key: str | None = None       # Google AI Overviews (P3)
    geo_extractor_model: str = "gpt-4o-mini"   # modele extraction (distinct du collecteur)
    geo_runs_per_prompt: int = 3               # N runs par prompt par defaut
    geo_raw_answer_max_chars: int = 4000       # troncature avant stockage
    geo_extract_input_max_chars: int = 2000    # troncature avant envoi a l'extracteur

    # Trends — signal de demande de marche.
    # Ordre de selection du provider : DataForSEO > SearchApi > mock.
    # - DataForSEO (login+password) : provider primaire prevu au plan (non teste live)
    # - SearchApi.io (searchapi_key) : Google Trends reel, cle validee (searchapi.io,
    #   NE PAS confondre avec serpapi.com/serpapi_key qui sert au moteur GEO google_aio)
    # - sinon : provider mock (donnees deterministes, deployable sans cle)
    dataforseo_login: str | None = None
    dataforseo_password: str | None = None
    searchapi_key: str | None = None
    trends_cache_ttl_quick_seconds: int = 21600     # Quick Pulse : 6h
    trends_cache_ttl_trending_seconds: int = 1800   # Trending now : 30 min
    trends_default_country: str = "FR"
    trends_default_language: str = "fr"
    trends_max_seed_terms: int = 20                 # garde-fou sous-requetes / job

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
