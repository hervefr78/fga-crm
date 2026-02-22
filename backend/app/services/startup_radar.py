# =============================================================================
# FGA CRM - Startup Radar HTTP Client
# Client async pour l'API Startup Radar (veille startups)
# =============================================================================

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Timeout par defaut pour les requetes SR
SR_TIMEOUT = 30.0
# Taille de page max pour les listes SR
SR_PAGE_SIZE = 200


class StartupRadarError(Exception):
    """Erreur lors de la communication avec Startup Radar."""


class StartupRadarClient:
    """Client HTTP async pour l'API Startup Radar."""

    def __init__(
        self,
        base_url: str | None = None,
        email: str | None = None,
        password: str | None = None,
    ):
        self.base_url = (base_url or settings.startup_radar_api_url).rstrip("/")
        self.email = email or settings.startup_radar_email
        self.password = password or settings.startup_radar_password
        self._token: str | None = None

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    async def authenticate(self) -> str:
        """Authentification via POST /auth/login (form-urlencoded) → JWT."""
        if not self.email or not self.password:
            raise StartupRadarError(
                "Credentials SR manquants (STARTUP_RADAR_EMAIL / STARTUP_RADAR_PASSWORD)"
            )

        async with httpx.AsyncClient(timeout=SR_TIMEOUT) as client:
            resp = await client.post(
                f"{self.base_url}/auth/login",
                data={"username": self.email, "password": self.password},
            )

        if resp.status_code != 200:
            raise StartupRadarError(
                f"Echec auth SR: {resp.status_code} — {resp.text}"
            )

        data = resp.json()
        self._token = data["access_token"]
        logger.info("[StartupRadar] Authentification reussie")
        return self._token

    def _headers(self) -> dict[str, str]:
        """Headers avec le token JWT."""
        if not self._token:
            raise StartupRadarError("Non authentifie — appeler authenticate() d'abord")
        return {"Authorization": f"Bearer {self._token}"}

    # ------------------------------------------------------------------
    # Requetes generiques
    # ------------------------------------------------------------------

    async def _get(self, path: str, params: dict | None = None) -> dict | list | None:
        """GET generique avec gestion d'erreur."""
        async with httpx.AsyncClient(timeout=SR_TIMEOUT) as client:
            resp = await client.get(
                f"{self.base_url}{path}",
                headers=self._headers(),
                params=params,
            )

        if resp.status_code == 404:
            return None

        if resp.status_code != 200:
            raise StartupRadarError(
                f"Erreur SR GET {path}: {resp.status_code} — {resp.text}"
            )

        return resp.json()

    async def _get_all_pages(self, path: str, size: int = SR_PAGE_SIZE) -> list[dict]:
        """Recuperer toutes les pages d'un endpoint pagine."""
        all_items: list[dict] = []
        page = 1

        while True:
            data = await self._get(path, params={"page": page, "size": size})
            if data is None:
                break

            items = data.get("items", [])
            all_items.extend(items)

            total_pages = data.get("pages", 1)
            if page >= total_pages:
                break
            page += 1

        return all_items

    # ------------------------------------------------------------------
    # Endpoints specifiques
    # ------------------------------------------------------------------

    async def get_startups(self) -> list[dict]:
        """Recuperer toutes les startups (paginee automatiquement)."""
        return await self._get_all_pages("/startups")

    async def get_contacts(self) -> list[dict]:
        """Recuperer tous les contacts (pagine automatiquement)."""
        return await self._get_all_pages("/contacts")

    async def get_investors(self) -> list[dict]:
        """Recuperer tous les investisseurs (pagine automatiquement)."""
        return await self._get_all_pages("/investors")

    async def get_analysis(self, startup_id: str) -> dict | None:
        """Recuperer l'analyse messaging d'une startup."""
        return await self._get(f"/analysis/startup/{startup_id}")

    async def get_detailed_audit(self, startup_id: str) -> dict | None:
        """Recuperer l'audit detaille d'une startup."""
        return await self._get(f"/detailed-audit/{startup_id}")
