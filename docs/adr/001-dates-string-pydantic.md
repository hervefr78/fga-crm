# ADR-001 : Dates en string dans les schemas Pydantic

## Date
2026-02-24

## Statut
accepted

## Contexte
Les champs date (`due_date`, `expected_close_date`) transitent entre le frontend (JSON string) et le backend (SQLAlchemy `Date`/`DateTime` natif). Pydantic peut valider les deux formats, mais le choix impacte toute la chaine.

## Decision
Les schemas Pydantic stockent les dates comme `str`. La conversion `str → date` se fait dans la route avec `date.fromisoformat()` / `datetime.fromisoformat()` AVANT passage au model SQLAlchemy.

## Alternatives envisagees
- Pydantic `date` natif — rejetee parce que le frontend envoie des strings ISO et la deserialisation automatique Pydantic causait des erreurs subtiles avec asyncpg (`'str' has no attribute 'toordinal'`)
- Conversion dans le schema (validator) — rejetee parce que ca melange validation et transformation, et les schemas sont reutilises en reponse ou la date doit rester string

## Consequences
- Chaque route qui manipule des dates doit convertir explicitement
- Risque d'oubli → bug en prod (asyncpg DataError)
- Regle DC : verifier TOUS les champs date d'un schema lors d'une modification

## Fichiers impactes
- `backend/app/schemas/*.py` — dates en `str | None`
- `backend/app/api/v1/*.py` — conversion `fromisoformat()` dans chaque route
