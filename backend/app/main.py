# =============================================================================
# FGA CRM - FastAPI Main Entry Point
# =============================================================================

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.config import settings
from app.db.session import close_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    await init_db()
    yield
    await close_db()


def create_application() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="API for FGA CRM - Fast Growth Advisors CRM",
        docs_url="/docs" if settings.app_debug else None,
        redoc_url="/redoc" if settings.app_debug else None,
        openapi_url="/openapi.json" if settings.app_debug else None,
        lifespan=lifespan,
    )

    cors_origins = [
        "http://localhost:3300",
        "http://127.0.0.1:3300",
    ]
    if settings.cors_origins:
        cors_origins.extend(settings.cors_origins.split(","))

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_application()


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
    }


# =============================================================================
# Endpoint interne — debug de l'identité de la clé API
# GET /api/_internal/whoami
# =============================================================================

# Import différé pour éviter les cycles au démarrage
from app.core.deps import get_service_user  # noqa: E402
from app.models.user import User  # noqa: E402


@app.get("/api/_internal/whoami", tags=["Internal"])
async def whoami(
    request: Request,
    user: User = Depends(get_service_user),
) -> dict:
    """Retourne l'identité du service account associé à la clé API.

    Utile pour valider qu'une clé est bien configurée côté consommateur (MCP, Nomo-IA…).
    Requiert : Authorization: Bearer crm_xxx
    """
    scopes: list[str] = getattr(request.state, "api_key_scopes", [])
    key_name: str = getattr(request.state, "api_key_name", "unknown")

    return {
        "service": settings.app_name,
        "user_id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "is_service": user.is_service,
        "key_name": key_name,
        "scopes": scopes,
    }
