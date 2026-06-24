# =============================================================================
# FGA CRM - Compass-Core HTTP Client
# Client async pour l'API compass-core (relecture des drafts).
# La cle service est detenue cote serveur uniquement et ne doit JAMAIS etre
# loggee ni renvoyee au client.
# =============================================================================

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Timeout par defaut pour les requetes compass-core.
COMPASS_TIMEOUT = 30.0


class CompassNotConfiguredError(Exception):
    """compass_api_url et/ou compass_service_api_key non configures.

    Marque la condition "proxy desactive" — le routeur la traduit en 503.
    """


class CompassNotFoundError(Exception):
    """compass-core a renvoye un 404 (draft introuvable).

    Le routeur la traduit en 404.
    """


class CompassServiceError(Exception):
    """Erreur non-2xx (hors 404) de compass-core, ou erreur reseau.

    Le routeur la traduit en 502.
    """


class CompassClient:
    """Client HTTP async pour l'API compass-core.

    Base URL = {compass_api_url}/v1. Auth : Authorization: Bearer <service key>.
    Une seule instance est reutilisee (voir `get_compass_client`) — on ne cree
    pas de client par requete.
    """

    def __init__(
        self,
        api_url: str | None = None,
        service_api_key: str | None = None,
    ):
        # On lit les settings ici. La validation (vide -> not-configured) est
        # faite a chaque requete pour rester correct si la config change.
        self._api_url = (api_url if api_url is not None else settings.compass_api_url).rstrip("/")
        self._service_api_key = (
            service_api_key
            if service_api_key is not None
            else settings.compass_service_api_key
        )

    # ------------------------------------------------------------------
    # Configuration & helpers
    # ------------------------------------------------------------------

    @property
    def base_url(self) -> str:
        """Base URL versionnee : {compass_api_url}/v1."""
        return f"{self._api_url}/v1"

    def _ensure_configured(self) -> None:
        """Fail loud (DC2) si l'URL ou la cle service sont vides."""
        if not self._api_url or not self._service_api_key:
            # Ne JAMAIS logger la cle. On signale uniquement l'etat de config.
            logger.warning(
                "[Compass] Proxy non configure (url=%s, key=%s)",
                "set" if self._api_url else "empty",
                "set" if self._service_api_key else "empty",
            )
            raise CompassNotConfiguredError("compass not configured")

    def _headers(self) -> dict[str, str]:
        """Headers avec la cle service (jamais loggee)."""
        return {"Authorization": f"Bearer {self._service_api_key}"}

    # ------------------------------------------------------------------
    # Requetes generiques
    # ------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json: dict | None = None,
    ) -> dict | list:
        """Requete generique vers compass-core avec mapping d'erreurs.

        - 404 -> CompassNotFoundError
        - autre non-2xx ou erreur reseau -> CompassServiceError
        - not-configured -> CompassNotConfiguredError (avant tout appel reseau)
        """
        self._ensure_configured()

        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=COMPASS_TIMEOUT) as client:
                resp = await client.request(
                    method,
                    url,
                    headers=self._headers(),
                    params=params,
                    json=json,
                )
        except httpx.HTTPError as e:
            # Ne pas inclure les headers (donc la cle) dans le log.
            logger.error("[Compass] Erreur reseau %s %s: %s", method, path, e)
            raise CompassServiceError(f"compass network error: {e}") from e

        if resp.status_code == 404:
            raise CompassNotFoundError(f"compass 404 on {path}")

        if not (200 <= resp.status_code < 300):
            logger.error(
                "[Compass] Reponse non-2xx %s %s: %d",
                method,
                path,
                resp.status_code,
            )
            raise CompassServiceError(
                f"compass {method} {path}: {resp.status_code}"
            )

        return resp.json()

    # ------------------------------------------------------------------
    # Endpoints specifiques
    # ------------------------------------------------------------------

    async def list_pending_drafts(
        self, brand: str | None, max_age_hours: int
    ) -> list[dict]:
        """GET /v1/drafts/pending — liste des drafts a relire.

        `brand` et `max_age_hours` sont valides/bornes par le routeur en amont.
        """
        params: dict[str, object] = {"max_age_hours": max_age_hours}
        if brand is not None:
            params["brand"] = brand
        data = await self._request("GET", "/drafts/pending", params=params)
        # compass-core renvoie une liste pour cet endpoint.
        if not isinstance(data, list):
            raise CompassServiceError("compass /drafts/pending: liste attendue")
        return data

    async def list_drafts_by_status(
        self, status: str, brand: str | None, limit: int = 1000
    ) -> list[dict]:
        """GET /v1/drafts?status=&brand=&limit= — drafts filtres par statut.

        Debloque l'export HeyReach des drafts `approved` (le `/pending` ne
        renvoie que `to-review`). `status` est requis cote compass-core ;
        `brand` est optionnel ; `limit` est borne (1..1000) en amont par le
        routeur. compass-core renvoie une liste pour cet endpoint.
        """
        params: dict[str, object] = {"status": status, "limit": limit}
        if brand is not None:
            params["brand"] = brand
        data = await self._request("GET", "/drafts", params=params)
        if not isinstance(data, list):
            raise CompassServiceError("compass /drafts: liste attendue")
        return data

    async def get_draft(self, draft_id: str) -> dict:
        """GET /v1/drafts/{id} — un draft. 404 -> CompassNotFoundError."""
        data = await self._request("GET", f"/drafts/{draft_id}")
        if not isinstance(data, dict):
            raise CompassServiceError("compass /drafts/{id}: objet attendu")
        return data

    async def update_draft_status(
        self, draft_id: str, status: str, reviewer: str
    ) -> dict:
        """PATCH /v1/drafts/{id}/status — change le statut.

        `reviewer` est impose par l'appelant (current_user.email, DC18).
        404 -> CompassNotFoundError.
        """
        payload = {"status": status, "reviewer": reviewer}
        data = await self._request(
            "PATCH", f"/drafts/{draft_id}/status", json=payload
        )
        if not isinstance(data, dict):
            raise CompassServiceError("compass /drafts/{id}/status: objet attendu")
        return data


# Instance partagee — on ne cree pas de client par requete.
_compass_client: CompassClient | None = None


def get_compass_client() -> CompassClient:
    """Retourne l'instance partagee du client compass-core."""
    global _compass_client
    if _compass_client is None:
        _compass_client = CompassClient()
    return _compass_client
