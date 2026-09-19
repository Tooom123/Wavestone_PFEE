"""Evaluation par etage.

Les controles sont volontairement grossiers (le plan cite-t-il des colonnes pertinentes ?
la synthese s'appuie-t-elle sur les chiffres produits ?) : ils detectent les regressions
franches sans pretendre juger la finesse d'une analyse.
"""

from __future__ import annotations

from dataclasses import dataclass

from agent_data.eval.cases import EvalCase
from agent_data.rendering.synthesis import describe_artifacts
from agent_data.schemas import AnalysisPlan, Artifact


@dataclass
class CheckResult:
    """Resultat d'un controle."""

    passed: bool
    detail: str

    def __bool__(self) -> bool:
        return self.passed


def check_stage1(
    case: EvalCase, plan: AnalysisPlan, artifacts: list[Artifact]
) -> list[CheckResult]:
    """Controle l'etage 1 : le plan est-il pertinent, a-t-il produit des resultats ?"""
    results = [
        CheckResult(
            passed=plan.restated_question.strip() != ""
            and plan.restated_question.strip() != plan.question.strip(),
            detail="la question metier doit etre reformulee en question statistique",
        ),
        CheckResult(
            passed=len(plan.steps) >= 2,
            detail=f"plan trop court : {len(plan.steps)} etape(s)",
        ),
        CheckResult(
            passed=bool(artifacts),
            detail="aucun artefact produit",
        ),
    ]

    used = {c for step in plan.steps for c in step.columns}
    if case.expected_columns:
        hits = used & set(case.expected_columns)
        results.append(
            CheckResult(
                passed=bool(hits),
                detail=(
                    f"aucune colonne pertinente mobilisee (attendu une de "
                    f"{case.expected_columns}, obtenu {sorted(used)})"
                ),
            )
        )
    return results


def check_stage2(case: EvalCase, artifacts: list[Artifact], synthesis: str) -> list[CheckResult]:
    """Controle l'etage 2 : la synthese repond-elle, sans inventer de chiffres ?"""
    lowered = synthesis.lower()
    results = [
        CheckResult(
            passed=len(synthesis.split()) >= 15,
            detail=f"synthese trop courte ({len(synthesis.split())} mots)",
        ),
        CheckResult(
            passed="```" not in synthesis and "import " not in synthesis,
            detail="la synthese ne doit contenir ni code ni Markdown technique",
        ),
    ]
    if case.expected_terms:
        results.append(
            CheckResult(
                passed=any(t in lowered for t in case.expected_terms),
                detail=f"aucun terme attendu {case.expected_terms} dans la synthese",
            )
        )
    if artifacts:
        results.append(
            CheckResult(
                passed=_grounded(synthesis, artifacts),
                detail="aucun chiffre de la synthese ne provient des artefacts",
            )
        )
    return results


def _grounded(synthesis: str, artifacts: list[Artifact]) -> bool:
    """Vrai si au moins un nombre de la synthese apparait dans les artefacts.

    Controle grossier d'ancrage : il ne prouve pas l'absence d'hallucination, mais
    detecte une synthese entierement deconnectee des resultats.
    """
    import re

    source = describe_artifacts(artifacts, max_rows=100)
    numbers = {n for n in re.findall(r"\d+(?:[.,]\d+)?", synthesis) if len(n) > 1}
    if not numbers:
        return True  # une synthese sans chiffre n'est pas a rejeter ici
    return any(n.replace(",", ".")[:4] in source.replace(",", ".") for n in numbers)
