"""Garde-fous : faisabilite, cohérence, compteurs par agent et journal de suivi."""

from __future__ import annotations

import json
from pathlib import Path

import pydantic
import pytest

from agent_data import monitoring
from agent_data.cli import main as cli_main
from agent_data.config import Settings
from agent_data.eval import golden, metrics
from agent_data.eval.golden import GoldenCase
from agent_data.graph import RunTrace, Stage1
from agent_data.planner.planner import plan_analysis, render_profile
from agent_data.profiling import profile_csv
from agent_data.rendering import synthesize
from agent_data.schemas import AnalysisPlan, ExecutionResult, ExecutionStatus
from tests.conftest import FakeLLM, FakeSandbox

CODE = "```python\nprint('ok')\n```"
REFUS = json.dumps(
    {
        "question": "Combien de clients habitent à Paris ?",
        "restated_question": "Nombre de clients domiciliés à Paris",
        "answerable": False,
        "unanswerable_reason": "aucune colonne ne donne la ville des clients",
        "steps": [{"id": "s1", "goal": "g", "method": "m", "columns": ["Ville"]}],
    }
)


def _stage(llm: FakeLLM, sandbox: FakeSandbox, **overrides: object) -> Stage1:
    options = {"human_validation": False, **overrides}
    settings = Settings(_env_file=None, **options)  # type: ignore[arg-type]
    return Stage1(settings=settings, client=llm, sandbox=sandbox)  # type: ignore[arg-type]


# ------------------------------------------------------------------------- faisabilite


def test_question_hors_perimetre_arretee_avant_tout_calcul(csv_ventes: Path) -> None:
    sandbox = FakeSandbox([])
    trace = RunTrace()
    state = _stage(FakeLLM([REFUS]), sandbox).run("Paris ?", [csv_ventes], trace=trace)

    assert state.plan is not None and not state.plan.answerable
    assert state.plan.steps == []  # les etapes proposees malgre le refus sont ignorees
    assert sandbox.codes == [] and state.code is None
    assert trace.guardrail_counts() == {"planner": {"hors_perimetre": 1}}


def test_l_abstention_passe_le_golden_dataset() -> None:
    plan = AnalysisPlan(
        question="Combien de clients habitent à Paris ?",
        restated_question="Nombre de clients domiciliés à Paris",
        answerable=False,
        unanswerable_reason="aucune colonne ne donne la ville des clients",
    )
    answer = synthesize(plan, [], client=FakeLLM([]))  # aucun appel au LLM
    case = GoldenCase("hors_paris", "hors_perimetre", "personality", plan.question, golden.ABSTAIN)
    assert metrics.score_case(case, answer, []).passed


def test_un_plan_realisable_a_des_etapes() -> None:
    with pytest.raises(pydantic.ValidationError):
        AnalysisPlan(question="q", restated_question="q", steps=[])


def test_le_profil_donne_la_periode_couverte(csv_ventes: Path) -> None:
    profile = profile_csv(csv_ventes)
    date = profile.column("date")
    assert date is not None and date.date_range == ("2011-01-01", "2012-06-01")
    assert "du 2011-01-01 au 2012-06-01" in render_profile(profile)
    assert profile.column("montant").date_range is None  # type: ignore[union-attr]


def test_le_planificateur_recoit_la_consigne_de_faisabilite(csv_ventes: Path) -> None:
    llm = FakeLLM([REFUS])
    plan_analysis("Paris ?", [profile_csv(csv_ventes)], client=llm)
    assert '"answerable"' in llm.prompts[0]


# ----------------------------------------------------------------- compteurs par agent


def test_colonnes_inventees_comptees(
    csv_ventes: Path, plan: AnalysisPlan, ok_result: ExecutionResult
) -> None:
    payload = plan.model_dump(mode="json")
    payload["steps"][0]["columns"] = ["montant", "Ville", "Ville"]
    llm = FakeLLM([json.dumps(payload), CODE, '{"is_satisfactory": true, "issues": []}'])
    trace = RunTrace()
    _stage(llm, FakeSandbox([ok_result])).run("q", [csv_ventes], trace=trace)
    assert trace.guardrails == [
        {"agent": "planner", "name": "colonnes_inventees", "detail": "Ville"}
    ]


def test_flux_qui_mene_au_plafond(csv_ventes: Path, plan_json: str) -> None:
    failing = ExecutionResult(status=ExecutionStatus.ERROR, stderr="KeyError")
    events: list[dict] = []
    trace = RunTrace(listener=events.append)
    _stage(FakeLLM([plan_json] + [CODE] * 3), FakeSandbox([failing] * 3), max_iterations=2).run(
        "q", [csv_ventes], trace=trace
    )
    names = [(g["agent"], g["name"]) for g in trace.guardrails]
    assert names[0] == ("coder", "code_en_erreur")
    assert names[-1] == ("boucle", "plafond_iterations")
    assert trace.guardrail_counts()["coder"]["code_en_erreur"] == 2
    assert sum(e["kind"] == "guardrail" for e in events) == len(trace.guardrails)


def test_delai_depasse_impute_au_sandbox(csv_ventes: Path, plan_json: str) -> None:
    timeout = ExecutionResult(status=ExecutionStatus.TIMEOUT)
    trace = RunTrace()
    _stage(FakeLLM([plan_json, CODE]), FakeSandbox([timeout]), max_iterations=1).run(
        "q", [csv_ventes], trace=trace
    )
    assert trace.guardrail_counts()["sandbox"] == {"delai_depasse": 1}


def test_refus_humain_compte(csv_ventes: Path, plan_json: str) -> None:
    trace = RunTrace()
    stage = _stage(FakeLLM([plan_json]), FakeSandbox([]), human_validation=True)
    stage.run("q", [csv_ventes], approve_plan=lambda _s: False, trace=trace)
    assert trace.guardrail_counts() == {"humain": {"plan_refuse": 1}}


# -------------------------------------------------------------------- journal de suivi


def _g(agent: str, name: str) -> dict[str, str]:
    return {"agent": agent, "name": name, "detail": ""}


def test_journal_et_resume(tmp_path: Path, csv_ventes: Path) -> None:
    log = tmp_path / "g.jsonl"
    state = _stage(FakeLLM([REFUS]), FakeSandbox([])).run("Paris ?", [csv_ventes])
    monitoring.record(log, run_id="a", datasets=["ventes"], state=state,
                      guardrails=[_g("planner", "hors_perimetre")], seconds=3)  # fmt: skip
    flow = [_g("coder", "code_en_erreur")] * 2 + [_g("boucle", "plafond_iterations")]
    monitoring.record(log, run_id="b", datasets=["ventes"], state=state, guardrails=flow, seconds=9)
    monitoring.record(log, run_id="c", datasets=["ventes"], state=None, guardrails=[], seconds=1)

    entry = json.loads(log.read_text().splitlines()[0])
    assert entry["outcome"] == "hors_perimetre" and "question" not in entry  # aucune question

    summary = monitoring.summarize(log)
    assert summary.runs == 3
    assert summary.outcomes == {"hors_perimetre": 1, "plafond": 1, "erreur": 1}
    assert summary.by_agent["coder"] == 2
    assert summary.flows["coder:code_en_erreur x2 > boucle:plafond_iterations"] == 1
    text = summary.render()
    assert "plafond d'itérations atteint" in text and "coder / code_en_erreur" in text


def test_journal_absent() -> None:
    assert monitoring.summarize(Path("/nulle/part.jsonl")).render() == "Aucun run enregistre."


def test_commande_garde_fous(tmp_path: Path, capsys, monkeypatch) -> None:
    log = tmp_path / "g.jsonl"
    monitoring.record(log, run_id="a", datasets=["v"], state=None, guardrails=[], seconds=1)
    monkeypatch.setattr("sys.argv", ["agent-data", "garde-fous", "--log", str(log)])
    with pytest.raises(SystemExit) as exit_:
        cli_main()
    assert exit_.value.code == 0
    assert "1 run(s)" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("answerable", "expected"), [(None, True), ("false", False), ("true", True), (False, False)]
)
def test_reponse_du_planificateur_normalisee(csv_ventes: Path, answerable, expected) -> None:
    payload = json.loads(REFUS) | {"answerable": answerable, "unanswerable_reason": None}
    plan = plan_analysis("q", [profile_csv(csv_ventes)], client=FakeLLM([json.dumps(payload)]))
    assert plan.answerable is expected and plan.unanswerable_reason == ""
