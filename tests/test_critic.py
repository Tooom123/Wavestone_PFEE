"""Tests du critique.

Le groupe « expurgation » protege le parti pris central : une trace d'erreur repart vers
le LLM a l'iteration suivante, et pandas y recopie volontiers des valeurs du jeu de
donnees. Sans filtrage, la boucle de correction ferait fuiter les donnees.
"""

from __future__ import annotations

from agent_data.critic import review
from agent_data.critic.critic import _error_essentials, redact_data_values
from agent_data.schemas import (
    AnalysisPlan,
    AnalysisStep,
    Artifact,
    ExecutionResult,
    ExecutionStatus,
    Finding,
)
from tests.conftest import FakeLLM


def _plan() -> AnalysisPlan:
    return AnalysisPlan(
        question="q",
        restated_question="r",
        steps=[AnalysisStep(id="s1", goal="g", method="m")],
    )


def _artifact() -> Artifact:
    return Artifact(id="a1", step_id="s1", title="T", payload=Finding(statement="ok"))


# --- verdicts deterministes ------------------------------------------------


def test_erreur_jugee_sans_appeler_le_llm() -> None:
    llm = FakeLLM([])  # aucune reponse scriptee : un appel ferait echouer le test
    critique = review(
        _plan(), ExecutionResult(status=ExecutionStatus.ERROR, stderr="boom"), client=llm
    )
    assert not critique.is_satisfactory
    assert not critique.replan, "une erreur de code se corrige, elle ne se replanifie pas"


def test_timeout_suggere_de_simplifier() -> None:
    critique = review(_plan(), ExecutionResult(status=ExecutionStatus.TIMEOUT), client=FakeLLM([]))
    assert not critique.is_satisfactory
    assert "vectoris" in critique.suggestion or "echantillon" in critique.suggestion


def test_absence_d_artefact_rejetee() -> None:
    critique = review(
        _plan(), ExecutionResult(status=ExecutionStatus.SUCCESS, stdout="rien"), client=FakeLLM([])
    )
    assert not critique.is_satisfactory


def test_critique_illisible_accepte_le_resultat() -> None:
    """Un critique qui ne repond pas correctement ne doit pas bloquer le run."""
    execution = ExecutionResult(status=ExecutionStatus.SUCCESS, artifacts=[_artifact()])
    critique = review(_plan(), execution, client=FakeLLM(["je ne sais pas"]))
    assert critique.is_satisfactory


# --- expurgation des valeurs de donnees ------------------------------------


def test_valeur_citee_par_pandas_masquee() -> None:
    trace = "ValueError: could not convert string to float: '7590-VHVEG'"
    assert "7590-VHVEG" not in redact_data_values(trace)


def test_concatenation_de_valeurs_masquee() -> None:
    trace = "KeyError: " + "-".join(f"ID{i:05d}" for i in range(40))
    assert "ID00007" not in redact_data_values(trace)


def test_nom_de_colonne_preserve() -> None:
    """Les colonnes font partie du schema : le modele les connait deja par le profil."""
    trace = "KeyError: 'Order Date'"
    assert "Order Date" in redact_data_values(trace, known_columns={"Order Date"})


def test_chemin_de_fichier_preserve() -> None:
    trace = '  File "/workspace/code.py", line 17, in <module>'
    assert "/workspace/code.py" in redact_data_values(trace)


def test_message_d_erreur_conserve_malgre_la_troncature() -> None:
    """Le message d'exception est la seule info utile : il ne doit jamais etre tronque."""
    trace = "Traceback:\n" + "\n".join(f"  File 'x', line {i}" for i in range(50))
    trace += "\nTypeError: unsupported operand type"
    assert "TypeError: unsupported operand type" in _error_essentials(trace)


def test_critique_ne_fait_pas_fuiter_les_donnees() -> None:
    """Bout en bout : la critique renvoyee ne doit contenir aucune valeur du dataset."""
    stderr = "ValueError: could not convert string to float: '7590-VHVEG'"
    critique = review(
        _plan(),
        ExecutionResult(status=ExecutionStatus.ERROR, stderr=stderr),
        client=FakeLLM([]),
    )
    assert "7590-VHVEG" not in " ".join(critique.issues)
