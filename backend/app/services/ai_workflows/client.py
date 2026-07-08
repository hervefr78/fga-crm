# =============================================================================
# FGA CRM - Workflows IA : client LLM commun (OpenAI structured outputs)
# =============================================================================
"""Appel LLM partage par les workflows IA. Sortie JSON STRICTE : le schema
Pydantic est envoye en response_format (services/openai_strict, pattern GEO/
Trends) et la reponse est validee avant tout usage — pas de strip de ```json.

Erreurs typees (DC2) : AiWorkflowError apres epuisement des tentatives, avec
`kind` (api_error | parse_error) pour le journal ai_workflow_runs."""

from __future__ import annotations

import logging

from pydantic import BaseModel, ValidationError

from app.config import settings
from app.services.openai_strict import build_response_format

logger = logging.getLogger(__name__)

_TIMEOUT_S = 45.0
_MAX_ATTEMPTS = 3  # 1 appel + 2 retries (ValidationError ou erreur API transitoire)


class AiWorkflowError(Exception):
    """Echec d'un appel workflow IA apres retries."""

    def __init__(self, message: str, *, kind: str = "api_error") -> None:
        super().__init__(message)
        self.kind = kind  # api_error | parse_error (statuts ai_workflow_runs)


async def call_openai_structured[T: BaseModel](
    schema_model: type[T],
    *,
    system: str,
    user: str,
    name: str,
    temperature: float = 0.2,
) -> tuple[T, dict]:
    """Appelle OpenAI en JSON strict et retourne (objet valide, usage tokens).

    usage = {"input_tokens": int | None, "output_tokens": int | None}.
    Leve AiWorkflowError (kind api_error|parse_error) apres _MAX_ATTEMPTS.
    """
    if not settings.openai_api_key:
        raise AiWorkflowError("OpenAI non configure (openai_api_key manquante)")

    # Import tardif — la lib openai est lourde (pattern geo/extractor).
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=_TIMEOUT_S)
    response_format = build_response_format(schema_model, name=name)

    last_exc: Exception | None = None
    last_kind = "api_error"
    for attempt in range(_MAX_ATTEMPTS):
        try:
            resp = await client.chat.completions.create(
                model=settings.ai_workflows_model,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format=response_format,
            )
            content = ""
            if resp.choices and resp.choices[0].message:
                content = resp.choices[0].message.content or ""
            usage = {
                "input_tokens": getattr(resp.usage, "prompt_tokens", None),
                "output_tokens": getattr(resp.usage, "completion_tokens", None),
            }
            return schema_model.model_validate_json(content), usage
        except ValidationError as exc:
            last_exc, last_kind = exc, "parse_error"
            logger.warning(
                "[AI workflows] ValidationError tentative %d/%d : %s",
                attempt + 1, _MAX_ATTEMPTS, exc,
            )
        except Exception as exc:  # noqa: BLE001 — erreur API/reseau, on retente
            last_exc, last_kind = exc, "api_error"
            logger.warning(
                "[AI workflows] erreur tentative %d/%d : %r",
                attempt + 1, _MAX_ATTEMPTS, exc,
            )

    raise AiWorkflowError(
        f"Appel IA echoue apres {_MAX_ATTEMPTS} tentatives : {last_exc}", kind=last_kind
    )
