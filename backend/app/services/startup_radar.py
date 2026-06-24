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


class StartupRadarConflict(StartupRadarError):
    """Un audit/operation est deja en cours cote SR (HTTP 409)."""


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

    async def authenticate(self) -> str | None:
        """Authentification via POST /auth/login (form-urlencoded) → JWT.

        Si les credentials ne sont pas configures ou si l'auth echoue (ex: AUTH_DISABLED
        cote SR), on continue sans token — les requetes passent en mode anonyme.
        """
        if not self.email or not self.password:
            logger.info("[StartupRadar] Pas de credentials — mode anonyme")
            return None

        try:
            async with httpx.AsyncClient(timeout=SR_TIMEOUT) as client:
                resp = await client.post(
                    f"{self.base_url}/auth/login",
                    data={"username": self.email, "password": self.password},
                )

            if resp.status_code != 200:
                logger.warning(
                    "[StartupRadar] Auth echouee (%d) — fallback mode anonyme",
                    resp.status_code,
                )
                return None

            data = resp.json()
            self._token = data["access_token"]
            logger.info("[StartupRadar] Authentification reussie")
            return self._token

        except httpx.HTTPError as e:
            logger.warning("[StartupRadar] Auth erreur réseau (%s) — fallback mode anonyme", e)
            return None

    def _headers(self) -> dict[str, str]:
        """Headers avec le token JWT (vide si mode anonyme)."""
        if not self._token:
            return {}
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

    async def get_geo_audit(self, startup_id: str) -> dict | None:
        """Recuperer l'audit GEO d'une startup."""
        return await self._get(f"/geo-audit/{startup_id}")

    async def launch_diagnostic_audit(self, startup_id: str) -> dict:
        """Declencher un audit diagnostic complet cote SR (detaille + GEO +
        presentation), execute en arriere-plan par SR.

        Leve StartupRadarConflict si un audit tourne deja (SR 409),
        StartupRadarError sinon.
        """
        async with httpx.AsyncClient(timeout=SR_TIMEOUT) as client:
            resp = await client.post(
                f"{self.base_url}/analysis/diagnostic/{startup_id}",
                headers=self._headers(),
            )

        if resp.status_code == 409:
            raise StartupRadarConflict(
                "Un audit est deja en cours pour cette entreprise cote Startup Radar"
            )
        if resp.status_code not in (200, 201, 202):
            raise StartupRadarError(
                f"Erreur SR POST diagnostic {startup_id}: {resp.status_code} — {resp.text}"
            )
        return resp.json()

    async def get_diagnostic_status(self, startup_id: str) -> dict | None:
        """Statut de l'audit diagnostic SR en cours.

        None si aucun audit n'est en cours (SR renvoie 404 par design via _get).
        Sinon : {status: running|completed|failed, step, presentation_url, error}.
        """
        return await self._get(f"/analysis/diagnostic/{startup_id}/status")

    def get_detailed_audit_file_urls(self, startup_id: str) -> tuple[str, str]:
        """Construire les URLs de telechargement MD et DOCX de l'audit detaille.

        Retourne (md_download_url, docx_download_url) — URLs absolues SR.
        On les stocke systematiquement si l'audit detaille existe.
        """
        base = self.base_url
        md_url = f"{base}/detailed-audit/{startup_id}/download/markdown"
        docx_url = f"{base}/detailed-audit/{startup_id}/download/docx"
        return md_url, docx_url

    async def get_presentation(self, startup_id: str) -> dict | None:
        """Recuperer la presentation commerciale d'une startup (la plus recente).

        Retourne {slug, public_url, radar_axes, status} ou None.
        """
        data = await self._get(f"/presentations/{startup_id}")
        if not data:
            return None

        # L'endpoint renvoie une liste de presentations
        items = data if isinstance(data, list) else [data]
        # Prendre la plus recente completee
        for item in items:
            if item.get("status") == "completed":
                return item
        return None
