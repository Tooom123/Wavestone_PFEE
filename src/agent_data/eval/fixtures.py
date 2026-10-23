"""Artefacts de reference pour comparer des modeles sur un role donne.

Comparer deux modeles de redaction n'a de sens que s'ils recoivent **exactement** les memes
resultats : ces artefacts figes sont ce que l'etage 1 produit sur chaque cas (ordres de
grandeur realistes). C'est le benefice direct du decoupage en deux etages.
"""

from __future__ import annotations

from agent_data.schemas import Artifact, Finding, Table

_FIXTURES: dict[str, list[Artifact]] = {
    "churn_facteurs": [
        Artifact(
            id="a1",
            step_id="s1",
            title="Taux de depart par type de contrat",
            payload=Table(
                columns=["Contract", "taux_depart_pct", "clients"],
                rows=[
                    ["Month-to-month", 42.7, 3875],
                    ["One year", 11.3, 1473],
                    ["Two year", 2.8, 1695],
                ],
            ),
        ),
        Artifact(
            id="a2",
            step_id="s2",
            title="Facteurs les plus associes au depart",
            payload=Table(
                columns=["facteur", "importance"],
                rows=[["tenure", 0.21], ["MonthlyCharges", 0.17], ["Contract_Two year", 0.11]],
            ),
        ),
        Artifact(
            id="a3",
            step_id="s2",
            title="Les clients recents en contrat mensuel partent le plus",
            payload=Finding(
                statement="Les clients en contrat mensuel et de moins de 12 mois d'anciennete "
                "resilient le plus.",
                evidence="taux de depart 42,7 % en contrat mensuel contre 2,8 % sur deux ans ; "
                "AUC du modele 0,84",
                confidence=0.85,
            ),
        ),
    ],
    "ventes_qualite": [
        Artifact(
            id="a1",
            step_id="s1",
            title="Marge moyenne par commande et par annee",
            payload=Table(
                columns=["annee", "marge_moyenne", "ventes"],
                rows=[[2011, 131.2, 2_150_000], [2012, 98.7, 2_410_000]],
            ),
        ),
        Artifact(
            id="a2",
            step_id="s2",
            title="Marge par categorie",
            payload=Table(
                columns=["categorie", "marge_moyenne"],
                rows=[["Furniture", 68.4], ["Office Supplies", 212.1], ["Technology", 429.7]],
            ),
        ),
        Artifact(
            id="a3",
            step_id="s2",
            title="Furniture tire la marge vers le bas",
            payload=Finding(
                statement="Les ventes ont progresse mais la marge moyenne a baisse, "
                "principalement a cause de Furniture.",
                evidence="marge moyenne 131 EUR en 2011 contre 99 EUR en 2012 ; Furniture 68 EUR",
                confidence=0.9,
            ),
        ),
    ],
    "segments_clients": [
        Artifact(
            id="a1",
            step_id="s1",
            title="Profil moyen des 3 segments",
            payload=Table(
                columns=["segment", "clients", "revenu_moyen", "depenses_vin", "recence_jours"],
                rows=[
                    ["Premium", 412, 78_400, 612, 31],
                    ["Intermediaire", 953, 51_200, 238, 49],
                    ["Economes", 875, 29_900, 41, 52],
                ],
            ),
        ),
        Artifact(
            id="a2",
            step_id="s1",
            title="Trois profils de clients se degagent",
            payload=Finding(
                statement="Trois segments se distinguent nettement par le revenu et les depenses.",
                evidence="segment Premium : 18 % des clients, 612 EUR de vin en moyenne ; "
                "silhouette 0,41",
                confidence=0.75,
            ),
        ),
    ],
}

#: Resultats volontairement hors sujet : un bon critique doit les refuser.
OFF_TOPIC: list[Artifact] = [
    Artifact(
        id="x1",
        step_id="s1",
        title="Nombre de lignes du fichier",
        payload=Table(columns=["lignes"], rows=[[1000]]),
    )
]


def fixture_artifacts(case_id: str) -> list[Artifact]:
    """Artefacts de reference du cas `case_id`."""
    return list(_FIXTURES[case_id])
