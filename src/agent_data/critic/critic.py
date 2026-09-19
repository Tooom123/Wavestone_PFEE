"""Critique : relit le resultat d'execution et decide de la suite.

Sans critique, il ne reste qu'un pipeline : c'est ce noeud qui rend la demarche
*decidee* plutot que *deroulee*. Il tranche entre trois issues — resultat satisfaisant,
correction du code, ou retour au planificateur.

Une erreur d'execution est jugee sans appeler le LLM : c'est deterministe, plus rapide et
plus fiable que de demander son avis a un modele sur une stack trace.
"""

from __future__ import annotations

from agent_data.llm import LLMClient, get_client
from agent_data.llm.parsing import ParseError, extract_json
from agent_data.schemas import AnalysisPlan, Critique, ExecutionResult, ExecutionStatus

SYSTEM_PROMPT = """Tu relis le resultat d'une analyse de donnees et tu juges s'il repond \
vraiment a la question posee.

Tu es exigeant mais pragmatique : un resultat partiel mais correct et exploitable est \
acceptable. Tu reponds UNIQUEMENT par un objet JSON valide."""

_TEMPLATE = """Question analysee :
{question}

Plan suivi :
{steps}

Resultat de l'execution :
  sortie standard : {stdout}
  artefacts produits : {artifacts}

Juge ce resultat au format JSON strict :
{{
  "is_satisfactory": <true|false>,
  "issues": ["<probleme constate>"],
  "suggestion": "<correction concrete a apporter, si besoin>",
  "replan": <true si le plan lui-meme est a revoir, false si seul le code est a corriger>
}}"""


def review(
    plan: AnalysisPlan,
    execution: ExecutionResult,
    *,
    client: LLMClient | None = None,
) -> Critique:
    """Juge un resultat d'execution."""
    verdict = _judge_failure(execution)
    if verdict is not None:
        return verdict

    client = client or get_client()
    prompt = _TEMPLATE.format(
        question=plan.restated_question,
        steps="\n".join(f"  {s.id}. {s.goal}" for s in plan.steps),
        stdout=(execution.stdout or "(vide)")[:3000],
        artifacts=_describe_artifacts(execution),
    )
    try:
        payload = extract_json(client.complete(prompt, system=SYSTEM_PROMPT))
        return Critique.model_validate(payload)
    except (ParseError, ValueError):
        # Un critique illisible ne doit pas bloquer le run : on accepte le resultat,
        # qui a au moins produit des artefacts valides.
        return Critique(
            is_satisfactory=True,
            issues=["Critique illisible : resultat accepte par defaut."],
        )


def _judge_failure(execution: ExecutionResult) -> Critique | None:
    """Verdict deterministe pour les cas ou le LLM n'apporte rien."""
    if execution.status is ExecutionStatus.TIMEOUT:
        return Critique(
            is_satisfactory=False,
            issues=["Le code a depasse le temps imparti."],
            suggestion=(
                "Simplifier le calcul : echantillonner, eviter les boucles sur les lignes, "
                "preferer les operations vectorisees."
            ),
            replan=False,
        )
    if execution.status is ExecutionStatus.ERROR:
        return Critique(
            is_satisfactory=False,
            issues=[f"Le code a echoue : {execution.stderr[-1500:]}"],
            suggestion="Corriger l'erreur signalee par la trace.",
            replan=False,
        )
    if not execution.artifacts:
        return Critique(
            is_satisfactory=False,
            issues=["Aucun artefact n'a ete produit."],
            suggestion=(
                "Ecrire les resultats en JSON dans /workspace/out/ selon le contrat d'artefacts."
            ),
            replan=False,
        )
    return None


def _describe_artifacts(execution: ExecutionResult) -> str:
    """Decrit les artefacts sans reinjecter tout leur contenu dans le prompt."""
    if not execution.artifacts:
        return "(aucun)"
    lines = []
    for art in execution.artifacts:
        payload = art.payload
        detail = payload.kind
        if payload.kind == "table":
            detail = f"table {len(payload.rows)}x{len(payload.columns)} {payload.columns}"
        elif payload.kind == "finding":
            detail = f"constat : {payload.statement} ({payload.evidence})"
        lines.append(f"  - [{art.step_id}] {art.title} : {detail}")
    return "\n".join(lines)
