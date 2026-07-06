# =============================================================================
# FGA CRM - GEO Extractor (extraction structuree des marques)
# =============================================================================
"""Extraction structuree des marques citees dans une reponse generee par une IA.

Strictement separe du collecteur : le collecteur produit du texte brut, l'extracteur
le transforme en donnees structurees (ExtractionResult) via un LLM.

L'extracteur est TOUJOURS gpt-4o-mini (settings.geo_extractor_model), T=0,
json_schema strict — meme si le collecteur etait Claude ou Gemini. Cela garantit
une extraction deterministe et homogene quel que soit le moteur de collecte.
"""

import logging

from pydantic import ValidationError

from app.config import settings
from app.schemas.geo import ExtractionResult
from app.services.openai_strict import build_response_format

logger = logging.getLogger(__name__)

# Nombre total de tentatives (1 initiale + 2 retries sur ValidationError)
MAX_ATTEMPTS = 3

# Timeout de l'appel d'extraction
EXTRACT_TIMEOUT = 30.0

PROMPT_EXTRACTEUR = """
Tu es un extracteur de donnees. On te donne une reponse generee par une IA a une question.
Liste TOUTES les marques, entreprises ou produits nommes, dans leur ordre d'apparition.
Pour chacune :
- rang = position d'apparition (la 1ere marque nommee = 1)
- recommandee = true seulement si l'IA la met en avant / conseille activement
- sentiment = ton envers CETTE marque uniquement (pas le ton general de la reponse)
- justification = extrait court du texte (max 200 chars) justifiant le sentiment
N'invente aucune marque. Si aucune n'est citee, renvoie {"marques": []}.
""".strip()


class ExtractionError(Exception):
    """Echec de l'extraction apres epuisement des tentatives."""


async def extraire_marques(
    raw_answer: str, *, max_chars: int = 2000
) -> ExtractionResult:
    """Appeler gpt-4o-mini (T=0, json_schema strict) pour extraire les marques.

    - Tronque raw_answer a max_chars avant envoi (optimisation tokens)
    - Retry x2 si ValidationError Pydantic (3 tentatives au total)
    - Leve ExtractionError si echec apres retries

    Cas vide : un raw_answer vide retourne directement ExtractionResult(marques=[])
    sans appel LLM (DC2 — pas de retour silencieux, mais economie d'appel justifiee).
    """
    if not settings.openai_api_key:
        raise ExtractionError("OpenAI non configure (openai_api_key manquante)")

    text = (raw_answer or "").strip()
    if not text:
        logger.info("[GEO extractor] raw_answer vide — aucune marque a extraire")
        return ExtractionResult(marques=[])

    truncated = text[:max_chars]

    # Import tardif — la lib openai est lourde.
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=EXTRACT_TIMEOUT)
    response_format = build_response_format(ExtractionResult, name="extraction")

    last_exc: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            resp = await client.chat.completions.create(
                model=settings.geo_extractor_model,
                temperature=0,
                messages=[
                    {"role": "system", "content": PROMPT_EXTRACTEUR},
                    {"role": "user", "content": truncated},
                ],
                response_format=response_format,
            )
            content = ""
            if resp.choices and resp.choices[0].message:
                content = resp.choices[0].message.content or ""
            return ExtractionResult.model_validate_json(content)
        except ValidationError as exc:
            last_exc = exc
            logger.warning(
                "[GEO extractor] ValidationError tentative %d/%d : %s",
                attempt + 1, MAX_ATTEMPTS, exc,
            )
        except Exception as exc:  # noqa: BLE001 — erreur API/reseau, on relance
            last_exc = exc
            logger.warning(
                "[GEO extractor] erreur tentative %d/%d : %s",
                attempt + 1, MAX_ATTEMPTS, exc,
            )

    logger.error("[GEO extractor] echec apres %d tentatives : %s", MAX_ATTEMPTS, last_exc)
    raise ExtractionError(f"Extraction echouee apres {MAX_ATTEMPTS} tentatives : {last_exc}")
