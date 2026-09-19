"""Tests du harnais d'evaluation."""

from __future__ import annotations

from agent_data.eval import CASES, check_stage1, check_stage2
from agent_data.schemas import AnalysisPlan, AnalysisStep, Artifact, Table


def _case(family: str):
    return next(c for c in CASES if c.family == family)


def _plan(columns: list[str], steps: int = 2) -> AnalysisPlan:
    return AnalysisPlan(
        question="La qualite des ventes est-elle bonne ?",
        restated_question="Le CA 2012 depasse-t-il celui de 2011 ?",
        steps=[
            AnalysisStep(id=f"s{i}", goal="g", method="m", columns=columns)
            for i in range(1, steps + 1)
        ],
    )


def _artifacts() -> list[Artifact]:
    return [
        Artifact(
            id="a1",
            step_id="s1",
            title="CA",
            payload=Table(columns=["annee", "ca"], rows=[[2011, 250], [2012, 450]]),
        )
    ]


def test_les_trois_familles_sont_couvertes() -> None:
    assert {c.family for c in CASES} == {"classification", "descriptif", "clustering"}
    assert len({c.dataset for c in CASES}) == 3


def test_stage1_valide_un_bon_plan() -> None:
    case = _case("descriptif")
    results = check_stage1(case, _plan(["Sales", "Profit"]), _artifacts())
    assert all(results), [r.detail for r in results if not r]


def test_stage1_rejette_une_question_non_reformulee() -> None:
    case = _case("descriptif")
    plan = _plan(["Sales"])
    plan.restated_question = plan.question
    assert not check_stage1(case, plan, _artifacts())[0]


def test_stage1_rejette_un_plan_sans_colonne_pertinente() -> None:
    case = _case("descriptif")
    results = check_stage1(case, _plan(["Row ID"]), _artifacts())
    assert not results[-1]


def test_stage1_rejette_l_absence_d_artefact() -> None:
    case = _case("descriptif")
    assert not check_stage1(case, _plan(["Sales"]), [])[2]


def test_stage2_valide_une_bonne_synthese() -> None:
    case = _case("descriptif")
    synthesis = (
        "Les ventes progressent nettement : le chiffre d'affaires passe de 250 en 2011 "
        "a 450 en 2012, soit une marge en hausse sur la categorie principale."
    )
    results = check_stage2(case, _artifacts(), synthesis)
    assert all(results), [r.detail for r in results if not r]


def test_stage2_rejette_une_synthese_avec_du_code() -> None:
    case = _case("descriptif")
    synthesis = "Voici le resultat des ventes et de la marge : ```python\nimport pandas\n```" * 2
    assert not check_stage2(case, _artifacts(), synthesis)[1]


def test_stage2_rejette_une_synthese_hors_sol() -> None:
    """Des chiffres absents des artefacts signalent une synthese inventee."""
    case = _case("descriptif")
    synthesis = (
        "Les ventes atteignent 99999 unites cette annee selon une marge de 88888 "
        "euros sur la categorie concernee, ce qui reste tres eleve globalement."
    )
    assert not check_stage2(case, _artifacts(), synthesis)[-1]


def test_stage2_rejette_une_synthese_trop_courte() -> None:
    case = _case("descriptif")
    assert not check_stage2(case, _artifacts(), "Oui.")[0]
