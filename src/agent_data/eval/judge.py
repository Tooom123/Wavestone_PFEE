"""Juge LLM local pour la pertinence de la reponse (equivalent de « answer relevancy »).

Les faits chiffres ne disent pas si la reponse traite la question posee ou derive vers autre
chose. Un modele local note la pertinence de 1 a 5 ; rien ne sort du poste. Le juge est
optionnel (`scripts/run_golden.py --juge`) : il coute un appel LLM par question et sa note
est moins reproductible que les metriques deterministes.
"""

from __future__ import annotations

from dataclasses import dataclass

from agent_data.llm import LLMClient
from agent_data.llm.parsing import ParseError, extract_json

SYSTEM = (
    "Tu es un evaluateur exigeant. Tu notes si une reponse traite la question posee, "
    "sans juger l'exactitude des chiffres. Tu reponds uniquement en JSON."
)

PROMPT = """Question posee par un decideur :
{question}

Reponse de l'assistant d'analyse :
{answer}

Note la pertinence de la reponse de 1 a 5 :
5 = repond directement et completement a la question ;
3 = repond en partie, ou noie la reponse dans des informations annexes ;
1 = ne repond pas a la question.
Si les donnees ne permettent pas de repondre et que la reponse le dit clairement, note 5.

Reponds avec ce JSON et rien d'autre : {{"note": <1-5>, "raison": "<une phrase>"}}"""


@dataclass(frozen=True)
class Verdict:
    score: float  # de 0 (hors sujet) a 1 (pertinente)
    note: int
    reason: str


def judge_relevance(client: LLMClient, question: str, answer: str) -> Verdict | None:
    """Note la pertinence ; None si le juge ne renvoie pas de note exploitable."""
    raw = client.complete(PROMPT.format(question=question, answer=answer), system=SYSTEM)
    try:
        data = extract_json(raw)
        note = int(data["note"])
    except (ParseError, KeyError, TypeError, ValueError):
        return None
    if not 1 <= note <= 5:
        return None
    return Verdict(score=(note - 1) / 4, note=note, reason=str(data.get("raison", "")))
