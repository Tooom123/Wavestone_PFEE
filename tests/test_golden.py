"""Tests du golden dataset et de ses metriques, sans LLM ni Docker ni CSV reels."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pandas as pd
import pytest

from agent_data.eval import golden, metrics, report
from agent_data.eval.golden import Fact, GoldenCase
from agent_data.eval.judge import judge_relevance
from agent_data.schemas import Artifact, Finding, Table
from tests.conftest import FakeLLM

GOLDEN = Path(__file__).resolve().parent.parent / "docs/eval/golden.json"


# --------------------------------------------------------------- le jeu fige dans le depot


def test_le_golden_dataset_compte_24_questions_en_6_categories() -> None:
    cases = golden.load(GOLDEN)
    assert len(cases) == 24
    assert Counter(c.category for c in cases) == dict.fromkeys(golden.CATEGORIES, 4)
    assert len({c.id for c in cases}) == len(cases)
    assert {c.dataset for c in cases} == {"telco_churn", "superstore", "personality"}


def test_chaque_question_a_des_faits_verifiables() -> None:
    for case in golden.load(GOLDEN):
        assert case.facts, case.id
        for fact in case.facts:
            if case.category == "hors_perimetre":
                assert fact.kind == "abstain"
            else:
                assert fact.kind in ("number", "label") and fact.value is not None, case.id


def test_le_golden_dataset_correspond_aux_questions_du_code() -> None:
    from_code = [(q[0], q[1], q[2], q[3]) for q in golden.QUESTIONS]
    from_file = [(c.id, c.category, c.dataset, c.question) for c in golden.load(GOLDEN)]
    assert from_code == from_file  # sinon : relancer scripts/build_golden.py


def test_aller_retour_json(tmp_path: Path) -> None:
    cases = golden.load(GOLDEN)
    path = tmp_path / "g.json"
    golden.dump(cases, path)
    assert golden.load(path) == cases


# ------------------------------------------------- references calculees sur de faux jeux


@pytest.fixture
def frames() -> dict[str, pd.DataFrame]:
    telco = pd.DataFrame(
        {
            "Churn": ["Yes", "No", "No", "Yes"],
            "Contract": ["Month-to-month", "Two year", "One year", "Month-to-month"],
            "SeniorCitizen": [1, 0, 0, 0],
            "tenure": [2, 40, 30, 4],
            "MonthlyCharges": [80.0, 50.0, 60.0, 90.0],
            "PaymentMethod": ["Electronic check", "Mailed check", "Mailed check", "Mailed check"],
        }
    )
    superstore = pd.DataFrame(
        {
            "Order ID": [1, 2, 3, 4],
            "Order Date": pd.to_datetime(["2009-01-05", "2011-03-01", "2012-06-01", "2012-07-01"]),
            "Sales": [100.0, 200.0, 300.0, 400.0],
            "Profit": [10.0, 20.0, -5.0, 50.0],
            "Discount": [0.1, 0.0, 0.05, 0.02],
            "Customer Segment": ["Corporate", "Consumer", "Corporate", "Consumer"],
            "Region": ["West", "Atlantic", "West", "Atlantic"],
            "Product Sub-Category": ["Binders", "Chairs", "Paper", "Tables"],
        }
    )
    personality = pd.DataFrame(
        {
            "Income": [50000.0, None, 70000.0],
            "Kidhome": [1, 0, 0],
            "Teenhome": [0, 0, 0],
            "Dt_Customer": pd.to_datetime(["2012-01-01", "2013-01-01", "2013-05-01"]),
            **{c: [10, 20, 30] for c in golden.SPEND_COLUMNS},
        }
    )
    return {"telco_churn": telco, "superstore": superstore, "personality": personality}


def test_chaque_reference_tourne_et_rend_des_faits(frames: dict[str, pd.DataFrame]) -> None:
    for case_id, _category, dataset, _question, reference, _note in golden.QUESTIONS:
        facts, alternatives = golden.expected(reference(frames[dataset]))
        for fact_set in [facts, *alternatives]:
            assert fact_set and all(isinstance(f, Fact) for f in fact_set), case_id


def test_references_exactes_sur_un_cas_connu(frames: dict[str, pd.DataFrame]) -> None:
    by_id = {q[0]: q[4] for q in golden.QUESTIONS}
    [rate] = by_id["agr_churn"](frames["telco_churn"])
    assert rate.value == 50.0 and rate.unit == "%"
    label, total = by_id["cmp_segment"](frames["superstore"])
    assert (label.value, total.value) == ("Consumer", 600.0)
    assert "particuliers" in label.aliases
    [revenu] = by_id["agr_revenu"](frames["personality"])
    assert revenu.value == 60000.0  # le revenu manquant est ignore


def test_build_signale_un_jeu_absent() -> None:
    with pytest.raises(FileNotFoundError):
        golden.build(Path("/nulle/part"), lambda _dataset: None)


def test_reponse_de_reference_lisible() -> None:
    case = GoldenCase("x", "agregat", "telco_churn", "?", [Fact("taux", "number", 26.5, "%")])
    assert case.reference_answer == "taux : 26,5 %"
    abstain = GoldenCase("y", "hors_perimetre", "telco_churn", "?", list(golden.ABSTAIN))
    assert "ne permettent pas" in abstain.reference_answer


# ------------------------------------------------------------------------- les nombres


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("un taux de 26,5 %", 26.5),
        ("soit 26.5%", 26.5),
        ("14 915 601 € de ventes", 14_915_601),
        ("14,9 millions d'euros", 14_900_000),
        ("3,6 M€", 3_600_000),
        ("une corrélation de -0,04", -0.04),
        ("1 189 nouveaux clients", 1189),
    ],
)
def test_lecture_des_nombres(text: str, expected: float) -> None:
    assert any(v == pytest.approx(expected) for v in metrics.numbers_in(text))


def test_nombre_ambigu_lu_des_deux_facons() -> None:
    assert set(metrics.numbers_in("1,394 commandes")) == {1.394, 1394.0}


def test_pourcentage_accepte_en_ratio() -> None:
    fact = Fact("taux", "number", 26.54, "%")
    assert metrics.number_matches(fact, [0.2654])
    assert metrics.number_matches(fact, [26.5])  # arrondi de la reponse
    assert not metrics.number_matches(fact, [30.0])


def test_tolerance_absolue_pour_les_petites_valeurs() -> None:
    fact = Fact("corr", "number", -0.037, abs_tol=0.03)
    assert metrics.number_matches(fact, [-0.04])
    assert not metrics.number_matches(fact, [0.2])


def test_etiquettes_sans_accents_ni_casse_avec_traductions() -> None:
    fact = Fact("catégorie", "label", "Technology", aliases=("technologie",))
    assert metrics.label_matches(fact, "La catégorie TECHNOLOGIE domine.")
    assert metrics.label_matches(fact, "Technology, de loin.")
    assert not metrics.label_matches(fact, "Le mobilier domine.")


def test_detection_de_l_abstention() -> None:
    assert metrics.abstains("Les données ne contiennent pas d'information sur la ville.")
    assert metrics.abstains("Aucune colonne ne décrit la satisfaction.")
    assert not metrics.abstains("Le taux de résiliation est de 26,5 %.")


# ---------------------------------------------------------------------------- les scores


def _artifact(rows: list[list], columns: list[str]) -> Artifact:
    return Artifact(
        id="a1", step_id="s1", title="Résultat", payload=Table(columns=columns, rows=rows)
    )


CONTRAT = GoldenCase(
    "cmp_contrat",
    "comparaison",
    "telco_churn",
    "Le taux varie-t-il selon le contrat ?",
    [Fact("mensuel", "number", 42.71, "%"), Fact("deux ans", "number", 2.83, "%")],
)
ARTIFACTS = [_artifact([["Month-to-month", 0.4271], ["Two year", 0.0283]], ["Contract", "rate"])]


def test_reponse_parfaite() -> None:
    answer = "Les contrats mensuels résilient à 42,7 %, contre 2,8 % pour les contrats de deux ans."
    score = metrics.score_case(CONTRAT, answer, ARTIFACTS)
    assert score.passed and score.answer_correctness == 1.0
    assert score.context_recall == 1.0 and score.faithfulness == 1.0


def test_fait_perdu_par_la_synthese() -> None:
    score = metrics.score_case(CONTRAT, "Le contrat mensuel résilie à 42,7 %.", ARTIFACTS)
    assert not score.passed and score.answer_correctness == 0.5
    assert score.context_recall == 1.0  # l'etage 1 avait le chiffre : l'etage 2 l'a perdu
    assert score.missing == ["deux ans"]


def test_chiffre_invente_detecte() -> None:
    answer = "Le contrat mensuel résilie à 42,7 % et les autres à 17,3 %."
    score = metrics.score_case(CONTRAT, answer, ARTIFACTS)
    assert score.faithfulness == 0.5 and score.unsupported == [17.3]


def test_resultat_porte_par_un_constat() -> None:
    finding = Artifact(
        id="f",
        step_id="s",
        title="Constat",
        payload=Finding(statement="Le mensuel part plus", evidence="42,71 % contre 2,83 %"),
    )
    score = metrics.score_case(CONTRAT, "", [finding])
    assert score.context_recall == 1.0 and score.answer_correctness == 0.0


HORS = GoldenCase(
    "hors", "hors_perimetre", "personality", "Combien à Paris ?", list(golden.ABSTAIN)
)


def test_abstention_honnete() -> None:
    score = metrics.score_case(HORS, "Les données ne contiennent aucune information de ville.", [])
    assert score.passed and score.abstained and score.context_recall is None


def test_abstention_qui_invente_un_chiffre_echoue() -> None:
    answer = (
        "Les données ne contiennent pas la ville, mais environ 312,5 clients seraient parisiens."
    )
    score = metrics.score_case(HORS, answer, [])
    assert score.abstained and not score.passed


def test_reponse_hors_perimetre_qui_invente() -> None:
    assert not metrics.score_case(HORS, "Il y a 412 clients à Paris.", []).passed


def test_synthese_par_categorie() -> None:
    a = metrics.score_case(CONTRAT, "42,7 % et 2,8 %", ARTIFACTS)
    b = metrics.score_case(HORS, "Aucune donnée de localisation.", [])
    summary = metrics.summarize([a, b])
    assert summary["total"]["cases"] == 2 and summary["total"]["passed"] == 2
    assert summary["comparaison"]["context_recall"] == 1.0
    assert summary["hors_perimetre"]["context_recall"] is None


# ------------------------------------------------------------------- juge et rapport


def test_juge_note_la_pertinence() -> None:
    verdict = judge_relevance(FakeLLM(['{"note": 4, "raison": "Répond."}']), "Q ?", "R.")
    assert verdict is not None and verdict.note == 4 and verdict.score == 0.75


@pytest.mark.parametrize("raw", ["pas de json", '{"note": 9}', '{"raison": "x"}'])
def test_juge_inexploitable(raw: str) -> None:
    assert judge_relevance(FakeLLM([raw]), "Q ?", "R.") is None


def _result(score: metrics.CaseScore, **extra: object) -> dict:
    return {
        "id": CONTRAT.id,
        "category": CONTRAT.category,
        "question": CONTRAT.question,
        "reference": "x",
        "answer": "42,7 % seulement.",
        "error": "",
        "score": score.__dict__,
        "relevance": None,
        "seconds": 80.0,
        **extra,
    }


META = {"date": "2026-11-11", "models": "m", "minutes": 1.3}


def test_rapport_markdown() -> None:
    score = metrics.score_case(CONTRAT, "42,7 % seulement.", ARTIFACTS)
    text = report.render([_result(score)], META)
    assert "0 questions réussies sur 1" in text and "deux ans" in text
    assert "Pertinence" not in text and "RAGAS" not in text  # notes optionnelles absentes


def test_rapport_avec_juge_et_ragas() -> None:
    score = metrics.score_case(CONTRAT, "42,7 % seulement.", ARTIFACTS)
    ragas = {"faithfulness": 1.0, "answer_accuracy": 0.5}
    text = report.render([_result(score, relevance=0.75, ragas=ragas)], META | {"ragas_judge": "q"})
    assert "Pertinence (juge)" in text and "RAGAS fidélité" in text and "juge RAGAS : q" in text
    assert "| 75 % |" in text and "| 50 % |" in text


# ------------------------------------------- corrections apres le premier passage reel


def test_variation_ecrite_sans_signe() -> None:
    fact = Fact("variation 2010", "number", -15.67, "%", abs_tol=0.3, ignore_sign=True)
    assert metrics.number_matches(fact, metrics.numbers_in("une baisse d'environ 15,7 %"))
    assert not metrics.number_matches(fact, [8.2])


AMOUNTS = [Fact("ca 2009", "number", 4_209_139.0), Fact("ca 2010", "number", 3_549_681.0)]
VARIATIONS = [Fact("variation 2010", "number", -15.67, "%", abs_tol=0.3, ignore_sign=True)]
EVOLUTION = GoldenCase("tmp", "temporel", "superstore", "?", AMOUNTS, alternatives=[VARIATIONS])


def test_formulation_alternative_acceptee() -> None:
    score = metrics.score_case(EVOLUTION, "Le chiffre d'affaires recule de 15,7 % en 2010.", [])
    assert score.passed and score.missing == []


def test_sans_formulation_complete_les_manques_viennent_de_la_principale() -> None:
    score = metrics.score_case(EVOLUTION, "4 209 139 € en 2009.", [])
    assert not score.passed and score.missing == ["ca 2010"]


def test_le_golden_accepte_les_variations_annuelles() -> None:
    [case] = [c for c in golden.load(GOLDEN) if c.id == "tmp_ca_annuel"]
    assert case.alternatives and all(f.ignore_sign for f in case.alternatives[0])
    assert " — ou — " in case.reference_answer


def test_noms_traduits_acceptes() -> None:
    [case] = [c for c in golden.load(GOLDEN) if c.id == "cls_sous_categories"]
    answer = (
        "Téléphones et Communication, puis Machines de bureau, "
        "puis Classeurs et accessoires de classeurs."
    )
    assert metrics.score_case(case, answer, []).passed


def test_un_extrait_de_donnees_brutes_ne_compte_pas_comme_resultat() -> None:
    raw = _artifact([[i, 406.6 if i == 7 else i] for i in range(150)], ["ID", "Total"])
    case = GoldenCase("x", "comparaison", "personality", "?", [Fact("dépense", "number", 406.6)])
    assert metrics.score_case(case, "", [raw]).context_recall == 0.0
    assert (
        metrics.score_case(case, "", [_artifact([["avec", 406.6]], ["g", "m"])]).context_recall
        == 1.0
    )


def test_results_only_retire_les_tables_et_series_longues() -> None:
    from agent_data.schemas import Figure

    long_table = _artifact([[i] for i in range(101)], ["x"])
    figure = Artifact(
        id="f",
        step_id="s",
        title="Nuage",
        payload=Figure(spec={"data": [{"y": list(range(500))}, {"y": [1.5, 2.5]}]}),
    )
    kept = metrics.results_only([long_table, figure, ARTIFACTS[0]])
    assert [a.title for a in kept] == ["Nuage", "Résultat"]
    assert kept[0].payload.spec["data"] == [{"y": [1.5, 2.5]}]


SATISFACTION = GoldenCase(
    "hors_satisfaction", "hors_perimetre", "superstore", "Satisfaction ?", list(golden.ABSTAIN)
)


def test_abstention_suivie_d_un_substitut_chiffre_echoue() -> None:
    answer = (
        "Nous ne disposons pas d'une note de satisfaction ; le profit moyen, utilisé comme "
        "indicateur, est de 255,46 dans les Territoires du Nord-Ouest."
    )
    support = _artifact([["Northwest Territories", 255.46]], ["Region", "Profit"])
    score = metrics.score_case(SATISFACTION, answer, [support])
    assert score.abstained and not score.passed


def test_abstention_sans_chiffre_reussit() -> None:
    answer = "Nous ne disposons pas de note de satisfaction dans ces données."
    assert metrics.score_case(SATISFACTION, answer, []).passed
