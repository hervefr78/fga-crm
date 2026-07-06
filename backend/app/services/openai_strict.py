# =============================================================================
# FGA CRM - OpenAI structured outputs : adaptation de schema au mode strict
# =============================================================================
"""Helper partage pour les appels OpenAI en mode `structured outputs` (strict).

Le mode strict impose : chaque objet porte `additionalProperties: false` et liste
TOUTES ses proprietes dans `required` ; les mots-cles de validation JSON Schema non
supportes (minimum, maxLength, default...) provoquent un 400 "Invalid schema" et
doivent etre retires. On post-traite donc le schema Pydantic AVANT envoi.

Source unique (DC8) : utilise par geo/extractor.py et trends/recommender.py.
"""

from __future__ import annotations

# Mots-cles de validation non supportes par le mode strict d'OpenAI.
_STRICT_UNSUPPORTED_KEYS = frozenset({
    "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
    "minLength", "maxLength", "pattern", "format",
    "minItems", "maxItems", "multipleOf", "default",
})


def to_openai_strict(node: object) -> object:
    """Adapter un schema JSON (issu de Pydantic) aux contraintes du mode strict.

    - chaque objet -> `additionalProperties: false` + `required` exhaustif
    - retrait des mots-cles de validation non supportes
    Recursif (couvre $defs, items, anyOf). Mute le noeud en place et le retourne.
    """
    if isinstance(node, dict):
        for key in list(node.keys()):
            if key in _STRICT_UNSUPPORTED_KEYS:
                del node[key]
        if node.get("type") == "object" and "properties" in node:
            node["additionalProperties"] = False
            node["required"] = list(node["properties"].keys())
        for value in node.values():
            to_openai_strict(value)
    elif isinstance(node, list):
        for item in node:
            to_openai_strict(item)
    return node


def build_response_format(schema_model: type, *, name: str) -> dict:
    """response_format json_schema strict depuis un modele Pydantic (BaseModel)."""
    schema = schema_model.model_json_schema()
    to_openai_strict(schema)
    return {
        "type": "json_schema",
        "json_schema": {"name": name, "strict": True, "schema": schema},
    }
