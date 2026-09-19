"""Tests de l'etage 2 (restitution), independants de l'etage 1."""

from __future__ import annotations

import json

from agent_data.rendering import Report, describe_artifacts, synthesize
from agent_data.schemas import AnalysisPlan, AnalysisStep, Artifact, Figure, Finding, Table
from tests.conftest import FakeLLM


def _plan() -> AnalysisPlan:
    return AnalysisPlan(
        question="Les ventes sont-elles bonnes ?",
        restated_question="Le CA 2012 depasse-t-il celui de 2011 ?",
        assumptions=["'bonnes' = en croissance"],
        steps=[AnalysisStep(id="s1", goal="Comparer", method="agregation")],
    )


def _artifacts() -> list[Artifact]:
    return [
        Artifact(
            id="a1",
            step_id="s1",
            title="CA par annee",
            payload=Table(columns=["annee", "ca"], rows=[[2011, 250], [2012, 450]]),
        ),
        Artifact(
            id="a2",
            step_id="s1",
            title="Constat",
            payload=Finding(statement="Le CA progresse", evidence="+80%", confidence=0.9),
        ),
    ]


def test_description_contient_les_chiffres() -> None:
    text = describe_artifacts(_artifacts())
    assert "450" in text and "+80%" in text


def test_description_tronque_les_grandes_tables() -> None:
    big = [
        Artifact(
            id="a",
            step_id="s1",
            title="T",
            payload=Table(columns=["x"], rows=[[i] for i in range(100)]),
        )
    ]
    text = describe_artifacts(big, max_rows=5)
    assert "lignes supplementaires" in text
    assert text.count("\n  ") < 20


def test_figure_decrite_sans_son_contenu() -> None:
    art = [Artifact(id="f", step_id="s1", title="Courbe", payload=Figure(spec={"data": [1] * 500}))]
    text = describe_artifacts(art)
    assert "figure disponible" in text
    assert "500" not in text


def test_synthese_appelle_le_llm() -> None:
    llm = FakeLLM(["Les ventes progressent de 80% entre 2011 et 2012."])
    out = synthesize(_plan(), _artifacts(), client=llm)  # type: ignore[arg-type]
    assert "80%" in out
    # Les chiffres doivent etre fournis au modele, pas inventes par lui.
    assert "450" in llm.prompts[0]


def test_synthese_sans_artefact_ne_sollicite_pas_le_llm() -> None:
    llm = FakeLLM([])
    out = synthesize(_plan(), [], client=llm)  # type: ignore[arg-type]
    assert "aucun resultat" in out.lower()
    assert llm.prompts == []


def test_rapport_json_reversible() -> None:
    report = Report.build(_plan(), _artifacts(), "Synthese.")
    payload = json.loads(report.to_json())
    assert payload["question"] == "Les ventes sont-elles bonnes ?"
    assert len(payload["artifacts"]) == 2


def test_rapport_ecrit_sur_disque(tmp_path) -> None:
    out = tmp_path / "rapport.json"
    Report.build(_plan(), _artifacts(), "S.").to_json(out)
    assert json.loads(out.read_text(encoding="utf-8"))["synthesis"] == "S."


def test_rapport_markdown() -> None:
    md = Report.build(_plan(), _artifacts(), "Synthese.").to_markdown()
    assert md.startswith("# Les ventes sont-elles bonnes ?")
    assert "| annee | ca |" in md
    assert "'bonnes' = en croissance" in md


def test_identifiants_masques_avant_la_synthese() -> None:
    """Parti pris 1 : aucun identifiant client ne doit entrer dans le contexte du LLM."""
    rows = [[f"{i:04d}-ABCDE", 0.5 + i / 100] for i in range(40)]
    art = [
        Artifact(
            id="a",
            step_id="s1",
            title="Risque par client",
            payload=Table(columns=["customerID", "risque"], rows=rows),
        )
    ]
    text = describe_artifacts(art)
    assert "0001-ABCDE" not in text
    assert "identifiant masque" in text
    assert "0.5" in text, "les scores doivent rester lisibles"


def test_categories_metier_preservees() -> None:
    """Une categorie n'est pas un identifiant, meme si toutes ses valeurs sont distinctes."""
    art = [
        Artifact(
            id="a",
            step_id="s1",
            title="Marge par categorie",
            payload=Table(
                columns=["categorie", "marge"],
                rows=[["Furniture", 68.1], ["Office Supplies", 112.4], ["Technology", 429.2]],
            ),
        )
    ]
    text = describe_artifacts(art)
    assert "Furniture" in text and "Technology" in text


def test_artefact_stocke_conserve_les_identifiants() -> None:
    """Le masquage ne concerne que le prompt : le rapport garde les valeurs utiles."""
    rows = [[f"{i:04d}-ABCDE", 0.9] for i in range(40)]
    artifact = Artifact(
        id="a",
        step_id="s1",
        title="Risque",
        payload=Table(columns=["customerID", "risque"], rows=rows),
    )
    report = Report.build(_plan(), [artifact], "Synthese.")
    assert "0001-ABCDE" in report.to_json()
