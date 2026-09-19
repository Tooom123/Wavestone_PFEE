"""Cas d'evaluation, un par famille d'analyse du perimetre.

Le decoupage en deux etages n'a d'interet que s'ils sont evaluables separement :
  - etage 1 : question -> plan -> code -> artefacts (evalue par `check_stage1`)
  - etage 2 : artefacts -> synthese (evalue par `check_stage2`)
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EvalCase:
    """Un cas de test metier."""

    id: str
    dataset: str
    """Nom du dossier sous `data/`."""
    question: str
    family: str
    """classification | descriptif | clustering"""
    expected_columns: list[str] = field(default_factory=list)
    """Colonnes qu'un plan pertinent devrait mobiliser (au moins une)."""
    expected_terms: list[str] = field(default_factory=list)
    """Termes attendus dans la synthese finale (au moins un)."""


CASES: list[EvalCase] = [
    EvalCase(
        id="churn_facteurs",
        dataset="telco_churn",
        question="Quels clients risquent de resilier leur abonnement, et pour quelles raisons ?",
        family="classification",
        expected_columns=["Churn", "tenure", "MonthlyCharges", "Contract"],
        expected_terms=["churn", "resili", "client"],
    ),
    EvalCase(
        id="ventes_qualite",
        dataset="superstore",
        question=(
            "La qualite des ventes s'est-elle amelioree entre 2011 et 2012, "
            "et quelles categories tirent la marge vers le bas ?"
        ),
        family="descriptif",
        expected_columns=["Sales", "Profit", "Order Date", "Product Category"],
        expected_terms=["vente", "marge", "categorie", "profit"],
    ),
    EvalCase(
        id="segments_clients",
        dataset="personality",
        question="Quels grands profils de clients se degagent selon leurs depenses ?",
        family="clustering",
        expected_columns=["Income", "MntWines", "MntMeatProducts", "Recency"],
        expected_terms=["segment", "profil", "groupe", "client"],
    ),
]
