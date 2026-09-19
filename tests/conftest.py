"""Doublures partagees : elles permettent de tester la boucle sans LLM ni Docker."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_data.schemas import (
    AnalysisPlan,
    AnalysisStep,
    Artifact,
    ExecutionResult,
    ExecutionStatus,
    Table,
)


class FakeLLM:
    """Client LLM scripte : rend les reponses fournies, dans l'ordre."""

    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.prompts: list[str] = []

    def complete(self, prompt: str, *, system: str = "") -> str:
        self.prompts.append(prompt)
        if not self.responses:
            raise AssertionError("FakeLLM : plus de reponse scriptee disponible")
        return self.responses.pop(0)


class FakeSandbox:
    """Sandbox scripte : rend les resultats fournis, dans l'ordre."""

    def __init__(self, results: list[ExecutionResult]) -> None:
        self.results = list(results)
        self.codes: list[str] = []

    def run(self, code: str, datasets: list | None = None) -> ExecutionResult:
        self.codes.append(code)
        return self.results.pop(0) if self.results else _ok_result()


def _ok_result() -> ExecutionResult:
    return ExecutionResult(
        status=ExecutionStatus.SUCCESS,
        stdout="ok",
        artifacts=[
            Artifact(
                id="a1",
                step_id="s1",
                title="Resultat",
                payload=Table(columns=["a"], rows=[[1]]),
            )
        ],
    )


@pytest.fixture
def ok_result() -> ExecutionResult:
    return _ok_result()


@pytest.fixture
def plan() -> AnalysisPlan:
    return AnalysisPlan(
        question="Les ventes sont-elles bonnes ?",
        restated_question="Le chiffre d'affaires 2012 depasse-t-il celui de 2011 ?",
        assumptions=["'bonnes' = en croissance annuelle"],
        steps=[AnalysisStep(id="s1", goal="Comparer le CA annuel", method="agregation")],
    )


@pytest.fixture
def plan_json(plan: AnalysisPlan) -> str:
    return json.dumps(plan.model_dump(mode="json"))


@pytest.fixture
def csv_ventes(tmp_path: Path) -> Path:
    path = tmp_path / "ventes.csv"
    path.write_text(
        "date,produit,montant,region\n"
        "2011-01-01,clio,100,ouest\n"
        "2011-06-01,clio,150,est\n"
        "2012-01-01,clio,200,ouest\n"
        "2012-06-01,megane,250,est\n"
    )
    return path
