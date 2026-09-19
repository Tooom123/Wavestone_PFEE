"""Tests des contrats de donnees partages par les deux etages."""

import pytest
from pydantic import ValidationError

from agent_data.schemas import (
    AgentState,
    AnalysisPlan,
    AnalysisStep,
    Artifact,
    ColumnKind,
    ColumnProfile,
    DatasetProfile,
    ExecutionResult,
    ExecutionStatus,
    Figure,
    Finding,
    Table,
)


def _profile() -> DatasetProfile:
    return DatasetProfile(
        name="ventes",
        source_path="data/ventes/ventes.csv",
        row_count=1000,
        columns=[
            ColumnProfile(
                name="prix",
                kind=ColumnKind.NUMERIC,
                dtype="float64",
                null_count=10,
                null_ratio=0.01,
                unique_count=800,
            )
        ],
    )


def test_column_lookup_retourne_none_si_absente() -> None:
    profile = _profile()
    assert profile.column("prix") is not None
    assert profile.column("inconnue") is None


def test_null_ratio_hors_bornes_rejete() -> None:
    with pytest.raises(ValidationError):
        ColumnProfile(
            name="prix",
            kind=ColumnKind.NUMERIC,
            dtype="float64",
            null_count=0,
            null_ratio=1.5,
            unique_count=1,
        )


def test_champ_inconnu_rejete() -> None:
    """Les contrats sont stricts : un champ en trop doit echouer, pas passer en silence."""
    with pytest.raises(ValidationError):
        Finding(statement="ok", inattendu="x")


def test_plan_exige_au_moins_une_etape() -> None:
    with pytest.raises(ValidationError):
        AnalysisPlan(question="q", restated_question="q bien posee", steps=[])


def test_plan_valide() -> None:
    plan = AnalysisPlan(
        question="La qualite des ventes est-elle bonne ?",
        restated_question="Le panier moyen 2026 differe-t-il de celui de 2025 ?",
        assumptions=["'qualite' = panier moyen"],
        steps=[AnalysisStep(id="s1", goal="Comparer les paniers moyens", method="test de Student")],
    )
    assert plan.steps[0].id == "s1"


@pytest.mark.parametrize(
    "payload",
    [
        Table(columns=["a"], rows=[[1]]),
        Figure(spec={"data": [], "layout": {}}),
        Finding(statement="Les ventes progressent", evidence="+12%", confidence=0.8),
    ],
)
def test_artifact_accepte_chaque_type_de_payload(payload: Table | Figure | Finding) -> None:
    artifact = Artifact(id="a1", step_id="s1", title="Resultat", payload=payload)
    assert artifact.payload.kind == payload.kind


def test_artifact_roundtrip_json_preserve_le_type_de_payload() -> None:
    """Le contrat entre etages transite en JSON : le discriminant doit survivre."""
    artifact = Artifact(
        id="a1", step_id="s1", title="Repartition", payload=Table(columns=["a"], rows=[[1]])
    )
    reconstruit = Artifact.model_validate_json(artifact.model_dump_json())
    assert isinstance(reconstruit.payload, Table)
    assert reconstruit == artifact


def test_execution_ok_suit_le_statut() -> None:
    assert ExecutionResult(status=ExecutionStatus.SUCCESS).ok
    assert not ExecutionResult(status=ExecutionStatus.TIMEOUT).ok


def test_budget_epuise_au_plafond() -> None:
    state = AgentState(question="q", max_iterations=2)
    assert not state.budget_exhausted
    state.iteration = 2
    assert state.budget_exhausted
