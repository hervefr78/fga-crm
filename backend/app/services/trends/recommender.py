# =============================================================================
# FGA CRM - Trends : recommandations LLM (mode Profond)
# =============================================================================
"""Transforme les signaux normalises d'un rapport Trends en recommandations
actionnables (mots-cles a cibler, requetes a surveiller, angles de contenu) via
OpenAI (json_schema strict), orientees par un objectif (SEO/Ads/Contenu/Prospection).

Best-effort (DC7) : toute erreur (cle absente, timeout, schema invalide) -> None.
Le rapport Trends reste valide sans recommandations ; jamais d'echec de job pour
cette raison. Appele uniquement en mode Profond (cout/latence maitrises).
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from app.config import settings
from app.schemas.trends import TrendKeywordRec, TrendRecommendations, TrendWatchQuery
from app.services.openai_strict import build_response_format

logger = logging.getLogger(__name__)

_TIMEOUT_S = 30.0

# Bornes de sortie (DC1)
_MAX_TARGET_KEYWORDS = 8
_MAX_WATCH_QUERIES = 6
_MAX_CONTENT_ANGLES = 5
_MAX_TEXT_LEN = 400
# Borne d'entree : on ne passe au LLM qu'un extrait des signaux (tokens).
_MAX_QUERIES_IN = 12

# Consigne par objectif (oriente la reco). Cle vide -> veille generale.
_OBJECTIVE_GUIDANCE = {
    "seo": "Objectif SEO : privilegie les mots-cles a fort potentiel de referencement "
           "naturel (intention informationnelle/comparative, volume durable).",
    "ads": "Objectif Ads : privilegie les mots-cles a intention commerciale/transactionnelle "
           "pour des campagnes payantes (haute intention d'achat).",
    "content": "Objectif Contenu : privilegie des angles editoriaux et sujets de contenu "
               "(articles, guides) exploitant les tendances montantes.",
    "prospection": "Objectif Prospection B2B : identifie les signaux et sujets a exploiter "
                   "en approche commerciale (accroches, pain points emergents).",
}
_DEFAULT_GUIDANCE = "Objectif : veille de marche generale (mots-cles a cibler et a surveiller)."


class _LlmReco(BaseModel):
    """Schema de sortie strict attendu du LLM (l'objectif est ajoute cote serveur)."""

    strategy: str
    target_keywords: list[TrendKeywordRec]
    watch_queries: list[TrendWatchQuery]
    content_angles: list[str]


def _clip(text: str) -> str:
    return (text or "").strip()[:_MAX_TEXT_LEN]


def _build_context(*, category_label: str, signals: dict, score: float) -> str:
    """Extrait compact des signaux pour le LLM (borne en taille)."""
    mp = signals.get("market_pulse", {})
    rising = signals.get("rising_queries", [])[:_MAX_QUERIES_IN]
    top = signals.get("top_queries", [])[:_MAX_QUERIES_IN]
    topics = signals.get("related_topics", [])[:_MAX_QUERIES_IN]

    lines = [
        f"Categorie / sujet : {category_label}",
        f"Score d'opportunite : {score}/100",
        f"Interet marche : {mp.get('interest_index')} (direction {mp.get('direction')})",
        "",
        "Requetes en hausse (query | croissance% | breakout) :",
    ]
    for q in rising:
        g = q.get("growth")
        lines.append(f"- {q.get('query')} | {g if g is not None else '—'} | {q.get('breakout')}")
    lines += ["", "Requetes dominantes :"]
    lines += [f"- {q.get('query')}" for q in top]
    if topics:
        lines += ["", "Sujets connexes :"]
        lines += [f"- {t.get('topic')}" for t in topics]
    return "\n".join(lines)


async def generate_recommendations(
    *,
    category_label: str,
    signals: dict,
    score: float,
    objective: str | None,
    language: str = "fr",
) -> TrendRecommendations | None:
    """Genere des recommandations via OpenAI. None si non configure ou en cas d'echec
    (best-effort — ne fait jamais echouer le job Trends appelant)."""
    if not settings.openai_api_key:
        logger.info("[Trends recommender] OpenAI non configure -> pas de recommandations")
        return None

    guidance = _OBJECTIVE_GUIDANCE.get(objective or "", _DEFAULT_GUIDANCE)
    lang = "francais" if language == "fr" else language
    system = (
        "Tu es un analyste growth B2B. A partir de signaux de demande de recherche "
        f"(Google Trends), tu produis des recommandations ACTIONNABLES et concises, en {lang}. "
        f"{guidance} Ne recommande que des mots-cles/requetes presents ou directement derives "
        "des signaux fournis. Reste factuel, pas de remplissage."
    )
    context = _build_context(category_label=category_label, signals=signals, score=score)

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=_TIMEOUT_S)
        resp = await client.chat.completions.create(
            model=settings.trends_llm_model,
            temperature=0.3,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": context},
            ],
            response_format=build_response_format(_LlmReco, name="trend_recommendations"),
        )
        content = ""
        if resp.choices and resp.choices[0].message:
            content = resp.choices[0].message.content or ""
        parsed = _LlmReco.model_validate_json(content)
    except Exception as exc:  # noqa: BLE001 — best-effort, degradation propre (DC7)
        logger.warning("[Trends recommender] echec generation : %r", exc)
        return None

    # Bornage des sorties + clip texte (DC1).
    return TrendRecommendations(
        strategy=_clip(parsed.strategy),
        objective=objective,
        target_keywords=[
            TrendKeywordRec(
                keyword=_clip(k.keyword), cluster=_clip(k.cluster), rationale=_clip(k.rationale),
            )
            for k in parsed.target_keywords[:_MAX_TARGET_KEYWORDS]
        ],
        watch_queries=[
            TrendWatchQuery(query=_clip(w.query), reason=_clip(w.reason))
            for w in parsed.watch_queries[:_MAX_WATCH_QUERIES]
        ],
        content_angles=[_clip(a) for a in parsed.content_angles[:_MAX_CONTENT_ANGLES]],
    )
