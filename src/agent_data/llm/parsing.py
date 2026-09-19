"""Extraction de contenu structure depuis une reponse de LLM.

Un modele local encadre volontiers sa reponse de texte ou de balises Markdown, meme
lorsqu'on lui demande du JSON strict. Plutot que de durcir le prompt indefiniment, on
tolere ces enrobages a la lecture.
"""

from __future__ import annotations

import json
import re
from typing import Any

_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)
_PY_FENCE = re.compile(r"```(?:python|py)?\s*(.*?)```", re.DOTALL)


class ParseError(ValueError):
    """La reponse du modele n'a pas pu etre interpretee."""


def extract_json(text: str) -> dict[str, Any]:
    """Extrait le premier objet JSON d'une reponse de LLM."""
    for candidate in _json_candidates(text):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise ParseError(f"Aucun objet JSON exploitable dans la reponse : {text[:300]!r}")


def _json_candidates(text: str) -> list[str]:
    """Retourne les fragments susceptibles d'etre du JSON, du plus probable au moins."""
    candidates = [block.strip() for block in _JSON_FENCE.findall(text)]
    candidates.append(text.strip())
    # Dernier recours : du premier '{' au dernier '}'.
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])
    return candidates


def extract_python(text: str) -> str:
    """Extrait le code Python d'une reponse de LLM."""
    blocks = _PY_FENCE.findall(text)
    if blocks:
        return blocks[0].strip()
    cleaned = text.strip()
    if not cleaned:
        raise ParseError("Le modele n'a retourne aucun code.")
    return cleaned
