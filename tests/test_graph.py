"""Tests de la boucle agentique (etage 1), sans LLM ni Docker reels."""

from __future__ import annotations

import json
from pathlib import Path

from agent_data.config import Settings
from agent_data.graph import RunTrace, Stage1
from agent_data.schemas import AnalysisPlan, ExecutionResult, ExecutionStatus
from tests.conftest import FakeLLM, FakeSandbox

CODE = "```python\nprint('ok')\n```"


def _stage(llm: FakeLLM, sandbox: FakeSandbox, **overrides: object) -> Stage1:
    settings = Settings(_env_file=None, human_validation=False, **overrides)  # type: ignore[arg-type]
    return Stage1(settings=settings, client=llm, sandbox=sandbox)  # type: ignore[arg-type]


def test_run_nominal(csv_ventes: Path, plan_json: str, ok_result: ExecutionResult) -> None:
    """Chemin heureux : plan, code, execution, critique satisfaite."""
    llm = FakeLLM([plan_json, CODE, '{"is_satisfactory": true, "issues": []}'])
    stage = _stage(llm, FakeSandbox([ok_result]))
    trace = RunTrace()

    state = stage.run("Les ventes sont-elles bonnes ?", [csv_ventes], trace=trace)

    assert state.iteration == 1
    assert state.artifacts and state.artifacts[0].id == "a1"
    assert not state.errors
    assert any("accepte" in e for e in trace.events)


def test_correction_apres_echec(csv_ventes: Path, plan_json: str, ok_result) -> None:
    """Une execution en erreur doit declencher une correction, pas un abandon."""
    failed = ExecutionResult(status=ExecutionStatus.ERROR, stderr="KeyError: 'montant'")
    # L'echec est juge sans appeler le LLM : pas de reponse de critique a scripter.
    llm = FakeLLM([plan_json, CODE, CODE, '{"is_satisfactory": true, "issues": []}'])
    sandbox = FakeSandbox([failed, ok_result])
    stage = _stage(llm, sandbox)

    state = stage.run("q", [csv_ventes])

    assert state.iteration == 2
    assert state.artifacts
    # Le second prompt de generation doit contenir l'erreur a corriger.
    assert "KeyError" in llm.prompts[2]


def test_plafond_d_iterations_respecte(csv_ventes: Path, plan_json: str) -> None:
    """Un critique jamais satisfait ne doit pas boucler indefiniment."""
    failing = ExecutionResult(status=ExecutionStatus.ERROR, stderr="boom")
    llm = FakeLLM([plan_json] + [CODE] * 10)
    sandbox = FakeSandbox([failing] * 10)
    stage = _stage(llm, sandbox, max_iterations=3)

    state = stage.run("q", [csv_ventes])

    assert state.iteration == 3
    assert len(sandbox.codes) == 3
    assert state.errors and "Plafond" in state.errors[0]


def test_replanification(csv_ventes: Path, plan_json: str, ok_result) -> None:
    """Quand le critique demande un replan, le planificateur est rappele."""
    llm = FakeLLM(
        [
            plan_json,
            CODE,
            json.dumps({"is_satisfactory": False, "issues": ["hors sujet"], "replan": True}),
            plan_json,
            CODE,
            '{"is_satisfactory": true, "issues": []}',
        ]
    )
    # Les deux executions produisent un artefact : le verdict passe donc par le LLM,
    # qui demande une replanification au premier tour.
    sandbox = FakeSandbox([ok_result, ok_result])
    stage = _stage(llm, sandbox)

    state = stage.run("q", [csv_ventes])

    assert state.iteration == 2
    assert isinstance(state.plan, AnalysisPlan)
    assert len(sandbox.codes) == 2


def test_validation_humaine_refus(csv_ventes: Path, plan_json: str) -> None:
    """Un plan refuse arrete le run avant toute execution de code."""
    llm = FakeLLM([plan_json])
    sandbox = FakeSandbox([])
    settings = Settings(_env_file=None, human_validation=True)
    stage = Stage1(settings=settings, client=llm, sandbox=sandbox)  # type: ignore[arg-type]

    state = stage.run("q", [csv_ventes], approve_plan=lambda _: False)

    assert state.errors == ["Plan refuse par l'utilisateur."]
    assert sandbox.codes == [], "aucun code ne doit etre execute si le plan est refuse"


def test_colonnes_hallucinees_filtrees(csv_ventes: Path) -> None:
    """Une colonne inventee par le modele ne doit pas atteindre le generateur de code."""
    plan = {
        "question": "q",
        "restated_question": "q",
        "steps": [
            {
                "id": "s1",
                "goal": "g",
                "method": "m",
                "columns": ["montant", "colonne_inexistante"],
            }
        ],
    }
    llm = FakeLLM([json.dumps(plan), CODE, '{"is_satisfactory": true, "issues": []}'])
    stage = _stage(llm, FakeSandbox([]))

    state = stage.run("q", [csv_ventes])

    assert state.plan is not None
    assert state.plan.steps[0].columns == ["montant"]


def test_meilleurs_artefacts_conserves_malgre_l_echec_final(
    csv_ventes: Path, plan_json: str, ok_result: ExecutionResult
) -> None:
    """Une iteration tardive ratee ne doit pas effacer les resultats d'une precedente."""
    empty = ExecutionResult(status=ExecutionStatus.SUCCESS, stdout="rien")
    llm = FakeLLM(
        [plan_json] + [CODE, json.dumps({"is_satisfactory": False, "issues": ["insuffisant"]})] * 3
    )
    # iteration 1 : 1 artefact ; iterations 2 et 3 : aucun.
    sandbox = FakeSandbox([ok_result, empty, empty])
    stage = _stage(llm, sandbox, max_iterations=3)

    state = stage.run("q", [csv_ventes])

    assert state.errors, "le run doit signaler que le plafond est atteint"
    assert len(state.artifacts) == 1, "l'artefact de la premiere iteration doit survivre"
