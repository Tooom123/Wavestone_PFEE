"""Etage 2 : artefacts JSON -> synthese en langage naturel.

Cet etage ne voit que les artefacts produits par l'etage 1, jamais les donnees ni le code.
C'est ce qui le rend evaluable separement : a artefacts identiques, la synthese doit etre
reproductible.
"""

from __future__ import annotations

from agent_data.llm import LLMClient, get_client
from agent_data.schemas import AnalysisPlan, Artifact

SYSTEM_PROMPT = """Tu restitues des resultats d'analyse a un decideur non technique.

Regles :
- Tu reponds a la question posee, directement, des la premiere phrase.
- Tu t'appuies uniquement sur les resultats fournis : aucun chiffre invente.
- Tu rappelles les hypotheses retenues quand elles changent la lecture du resultat.
- Pas de jargon statistique inutile, pas de code, pas de Markdown."""

_TEMPLATE = """Question posee :
{question}

Reformulation analysee :
{restated}

Hypotheses retenues :
{assumptions}

Resultats obtenus :
{artifacts}

Redige la reponse au decideur en 3 a 6 phrases."""


def describe_artifacts(artifacts: list[Artifact], *, max_rows: int = 12) -> str:
    """Rend les artefacts sous forme lisible pour le prompt de synthese."""
    if not artifacts:
        return "(aucun resultat)"

    blocks: list[str] = []
    for art in artifacts:
        payload = art.payload
        if payload.kind == "table":
            head = " | ".join(payload.columns)
            rows = [" | ".join(str(v) for v in row) for row in payload.rows[:max_rows]]
            extra = (
                f"\n  ... ({len(payload.rows) - max_rows} lignes supplementaires)"
                if len(payload.rows) > max_rows
                else ""
            )
            blocks.append(f"[{art.title}]\n  {head}\n  " + "\n  ".join(rows) + extra)
        elif payload.kind == "finding":
            confidence = f" (confiance {payload.confidence:.0%})" if payload.confidence else ""
            blocks.append(f"[{art.title}] {payload.statement}{confidence} — {payload.evidence}")
        else:  # figure
            blocks.append(f"[{art.title}] figure disponible")
    return "\n\n".join(blocks)


def synthesize(
    plan: AnalysisPlan,
    artifacts: list[Artifact],
    *,
    client: LLMClient | None = None,
) -> str:
    """Produit la reponse en langage naturel destinee au decideur."""
    if not artifacts:
        return (
            "L'analyse n'a produit aucun resultat exploitable. "
            "La question doit etre reformulee ou les donnees completees."
        )

    client = client or get_client()
    prompt = _TEMPLATE.format(
        question=plan.question,
        restated=plan.restated_question,
        assumptions="\n".join(f"  - {a}" for a in plan.assumptions) or "  (aucune)",
        artifacts=describe_artifacts(artifacts),
    )
    return client.complete(prompt, system=SYSTEM_PROMPT)
