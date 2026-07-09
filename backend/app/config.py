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
    # Integration SR : plafond journalier de mesures audit-visibilite par cle service
    geo_audit_daily_quota: int = 100

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
    # Recommandations LLM (mode Profond) : reutilise openai_api_key. None -> desactive.
    trends_llm_model: str = "gpt-4o-mini"

    # Workflows IA natifs (scoring, qualification, insights — spec workflows-ia).
    # Reutilise openai_api_key (stack LLM unique). Kill switch global.
    ai_workflows_enabled: bool = True
    ai_workflows_model: str = "gpt-4o-mini"
    ai_score_ttl_days: int = 7                      # score deal en cache N jours

    # Lead Engine (orchestration leadgen — docs/LEAD_ENGINE_VISION.md).
    # Regle metier : MMF gap = seul declencheur d'outreach ; la levee de fonds
    # est un qualificateur de solvabilite (declenche un audit, jamais un contact).
    lead_engine_enabled: bool = True                # kill switch du scan periodique
    lead_engine_mmf_threshold: int = 30             # audit < seuil /75 -> signal mmf_gap
    lead_engine_funding_window_days: int = 30       # levee plus recente -> funding_detected
    lead_engine_dedup_days: int = 90                # anti re-declenchement par dedup_key

    # Enrichissement emails B2B (feature Compass). Icypeas = moteur principal ;
    # si cle absente -> provider mock (deployable/testable sans cle).
    icypeas_api_key: str | None = None
    icypeas_api_secret: str | None = None           # secret HMAC pour verifier les webhooks
    icypeas_webhook_verify: bool = True             # verifier la signature des callbacks
    icypeas_webhook_url: str | None = None          # URL publique du callback (prod)
    # Source societe pour l'enrichissement : "mock" (dev/tests) | "gouv" (API
    # recherche-entreprises.api.gouv.fr, gratuite, sans cle — CompanySource FR).
    enrichment_company_source: str = "mock"
    enrichment_bulk_timeout_hours: int = 24         # bulk sans callback -> reconcilie failed
    enrichment_daily_quota: int = 5000              # credits/jour par organisation
    enrichment_max_credits_per_run: int = 5000      # plafond par job
    enrichment_refresh_days: int = 60               # TTL fraicheur personne
    enrichment_people_refresh_days: int = 90        # TTL fraicheur sourcing societe
    enrichment_retention_days: int = 1095           # RGPD : retention 3 ans
    enrichment_second_pass_verify: float = 0.85     # seuil 2e passe (catch_all/risky)
    enrichment_catchall_accept: float = 0.90        # seuil acceptation catch_all

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
