"""Golden dataset : des questions metier dont la bonne reponse est connue.

Chaque question vient avec une fonction de reference qui calcule, avec pandas, les faits que
la reponse doit contenir. `scripts/build_golden.py` execute ces fonctions sur les vrais CSV
et fige le resultat dans `docs/eval/golden.json`, versionne et relisible. L'evaluation compare
ensuite les reponses de l'agent a ces valeurs figees : une reponse attendue ne change pas
sans que quelqu'un l'ait regeneree et relue.

Six categories, quatre questions chacune, sur les trois jeux de donnees du projet. La sixieme
categorie (« hors perimetre ») pose des questions auxquelles les donnees ne permettent pas de
repondre : la bonne reponse est de le dire, pas d'inventer.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

import pandas as pd

FactKind = Literal["number", "label", "abstain"]

CATEGORIES: dict[str, str] = {
    "agregat": "Statistique simple sur tout le jeu",
    "comparaison": "Comparaison entre groupes",
    "temporel": "Évolution dans le temps",
    "relation": "Lien entre deux variables",
    "classement": "Classement, meilleur ou pire",
    "hors_perimetre": "Question sans réponse dans les données",
}

SPEND_COLUMNS = [
    "MntWines",
    "MntFruits",
    "MntMeatProducts",
    "MntFishProducts",
    "MntSweetProducts",
    "MntGoldProds",
]


@dataclass(frozen=True)
class Fact:
    """Un element que la reponse doit contenir."""

    name: str
    kind: FactKind
    value: float | str | None = None
    unit: str = ""  # "%" : la valeur est en pourcentage (26,5 et 0,265 sont acceptes)
    rel_tol: float = 0.03  # ecart relatif admis (arrondis de la reponse)
    abs_tol: float | None = None  # ecart absolu admis, pour les petites valeurs
    aliases: tuple[str, ...] = ()  # autres ecritures d'une etiquette (traductions)


@dataclass(frozen=True)
class GoldenCase:
    id: str
    category: str
    dataset: str
    question: str
    facts: list[Fact] = field(default_factory=list)
    note: str = ""

    @property
    def reference_answer(self) -> str:
        """La reponse attendue, en clair, pour relecture humaine."""
        if any(f.kind == "abstain" for f in self.facts):
            return "Les données ne permettent pas de répondre ; la réponse doit le dire."
        parts = []
        for f in self.facts:
            if f.kind == "label":
                parts.append(f"{f.name} : {f.value}")
            else:
                value = float(f.value) if isinstance(f.value, int | float) else 0.0
                parts.append(f"{f.name} : {_fmt(value)}{' %' if f.unit == '%' else ''}")
        return " ; ".join(parts)


def _fmt(value: float) -> str:
    if float(value).is_integer() and abs(value) < 1000:
        return str(int(value))
    if abs(value) >= 1000:
        return f"{value:,.0f}".replace(",", " ")
    return f"{value:.3g}".replace(".", ",") if abs(value) < 1 else f"{value:.1f}".replace(".", ",")


# --------------------------------------------------------------------- donnees de reference


def load_frame(csv_path: Path) -> pd.DataFrame:
    """Charge un CSV du projet avec les conversions dont les references ont besoin."""
    df = pd.read_csv(csv_path, sep=None, engine="python")
    if "TotalCharges" in df:
        df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce")
    if "Order Date" in df:
        df["Order Date"] = pd.to_datetime(df["Order Date"], format="%m/%d/%Y")
    if "Dt_Customer" in df:
        df["Dt_Customer"] = pd.to_datetime(df["Dt_Customer"])
    return df


def _pct(mask: pd.Series) -> float:
    return float(mask.mean() * 100)


def _churn(df: pd.DataFrame) -> pd.Series:
    return df["Churn"] == "Yes"


def _num(name: str, value: float, **kw: Any) -> Fact:
    return Fact(name=name, kind="number", value=round(float(value), 4), **kw)


def _label(name: str, value: str, *aliases: str) -> Fact:
    return Fact(name=name, kind="label", value=value, aliases=aliases)


ABSTAIN = [Fact(name="reconnaît que les données ne le permettent pas", kind="abstain")]

Reference = Callable[[pd.DataFrame], list[Fact]]

# Traductions acceptees pour les etiquettes, dans l'ordre ou l'agent peut les ecrire.
LABEL_ALIASES: dict[str, tuple[str, ...]] = {
    "Technology": ("technologie", "technologique", "high-tech"),
    "Office Supplies": ("fournitures de bureau", "fournitures"),
    "Furniture": ("mobilier", "meubles"),
    "Corporate": ("entreprise", "entreprises", "grands comptes"),
    "Consumer": ("particuliers", "consommateurs", "grand public"),
    "Home Office": ("bureau a domicile", "teletravail"),
    "Small Business": ("petites entreprises", "tpe", "pme"),
    "Electronic check": ("cheque electronique",),
    "Month-to-month": ("mensuel", "sans engagement", "mois par mois", "au mois"),
    "MntWines": ("vin", "vins", "wine", "wines"),
    "MntMeatProducts": ("viande", "viandes", "meat"),
    "West": ("ouest",),
}


def _labelled(name: str, value: str) -> Fact:
    return _label(name, value, *LABEL_ALIASES.get(value, ()))


def _ref_taux_global(df: pd.DataFrame) -> list[Fact]:
    return [_num("taux de résiliation", _pct(_churn(df)), unit="%")]


def _ref_ca_profit(df: pd.DataFrame) -> list[Fact]:
    return [
        _num("chiffre d'affaires total", df["Sales"].sum()),
        _num("profit total", df["Profit"].sum()),
    ]


def _ref_revenu(df: pd.DataFrame) -> list[Fact]:
    return [_num("revenu annuel moyen", df["Income"].mean())]


def _ref_facture(df: pd.DataFrame) -> list[Fact]:
    return [_num("facture mensuelle moyenne", df["MonthlyCharges"].mean())]


def _ref_contrat(df: pd.DataFrame) -> list[Fact]:
    rates = df.groupby("Contract")["Churn"].apply(lambda s: _pct(s == "Yes"))
    return [_num(f"taux de résiliation ({k})", v, unit="%") for k, v in rates.items()]


def _ref_seniors(df: pd.DataFrame) -> list[Fact]:
    rates = df.groupby("SeniorCitizen")["Churn"].apply(lambda s: _pct(s == "Yes"))
    return [
        _num("taux de résiliation des seniors", rates[1], unit="%"),
        _num("taux de résiliation des autres", rates[0], unit="%"),
    ]


def _ref_enfants(df: pd.DataFrame) -> list[Fact]:
    spend = df[SPEND_COLUMNS].sum(axis=1)
    kids = (df["Kidhome"] + df["Teenhome"]) > 0
    return [
        _num("dépense moyenne avec enfants", spend[kids].mean()),
        _num("dépense moyenne sans enfants", spend[~kids].mean()),
    ]


def _ref_segment(df: pd.DataFrame) -> list[Fact]:
    sales = df.groupby("Customer Segment")["Sales"].sum().sort_values(ascending=False)
    return [
        _labelled("segment le plus important", str(sales.index[0])),
        _num("son chiffre d'affaires", sales.iloc[0]),
    ]


def _ref_ca_annuel(df: pd.DataFrame) -> list[Fact]:
    sales = df.groupby(df["Order Date"].dt.year)["Sales"].sum()
    return [_num(f"chiffre d'affaires {y}", v) for y, v in sales.items()]


def _ref_profit_2011_2012(df: pd.DataFrame) -> list[Fact]:
    profit = df.groupby(df["Order Date"].dt.year)["Profit"].sum()
    return [_num("profit 2011", profit[2011]), _num("profit 2012", profit[2012])]


def _ref_recrutement(df: pd.DataFrame) -> list[Fact]:
    counts = df.groupby(df["Dt_Customer"].dt.year).size()
    return [_num(f"nouveaux clients {y}", n) for y, n in counts.items()]


def _ref_commandes(df: pd.DataFrame) -> list[Fact]:
    orders = df.groupby(df["Order Date"].dt.year)["Order ID"].nunique().sort_values()
    return [
        _label("année avec le plus de commandes", str(orders.index[-1])),
        _num("nombre de commandes cette année-là", orders.iloc[-1]),
    ]


def _ref_anciennete(df: pd.DataFrame) -> list[Fact]:
    tenure = df.groupby("Churn")["tenure"].mean()
    return [
        _num("ancienneté moyenne des partants (mois)", tenure["Yes"]),
        _num("ancienneté moyenne des fidèles (mois)", tenure["No"]),
    ]


def _ref_revenu_vin(df: pd.DataFrame) -> list[Fact]:
    corr = df["Income"].corr(df["MntWines"])
    return [_num("corrélation revenu / vin", corr, abs_tol=0.03)]


def _ref_remise_profit(df: pd.DataFrame) -> list[Fact]:
    corr = df["Discount"].corr(df["Profit"])
    return [_num("corrélation remise / profit", corr, abs_tol=0.03)]


def _ref_facture_churn(df: pd.DataFrame) -> list[Fact]:
    charges = df.groupby("Churn")["MonthlyCharges"].mean()
    return [
        _num("facture moyenne des partants", charges["Yes"]),
        _num("facture moyenne des fidèles", charges["No"]),
    ]


def _ref_top_sous_categories(df: pd.DataFrame) -> list[Fact]:
    top = df.groupby("Product Sub-Category")["Profit"].sum().nlargest(3)
    return [_label(f"n°{i} des sous-catégories", str(k)) for i, k in enumerate(top.index, 1)]


def _ref_region(df: pd.DataFrame) -> list[Fact]:
    sales = df.groupby("Region")["Sales"].sum().sort_values(ascending=False)
    return [_labelled("région en tête", str(sales.index[0])), _num("ses ventes", sales.iloc[0])]


def _ref_depense_categorie(df: pd.DataFrame) -> list[Fact]:
    totals = df[SPEND_COLUMNS].sum().sort_values(ascending=False)
    return [
        _labelled("catégorie la plus dépensée", str(totals.index[0])),
        _num("dépense totale dans cette catégorie", totals.iloc[0]),
    ]


def _ref_paiement(df: pd.DataFrame) -> list[Fact]:
    rates = df.groupby("PaymentMethod")["Churn"].apply(lambda s: _pct(s == "Yes"))
    rates = rates.sort_values(ascending=False)
    return [
        _labelled("moyen de paiement le plus exposé", str(rates.index[0])),
        _num("son taux de résiliation", rates.iloc[0], unit="%"),
    ]


def _abstain(_df: pd.DataFrame) -> list[Fact]:
    return list(ABSTAIN)


QUESTIONS: list[tuple[str, str, str, str, Reference, str]] = [
    # id, categorie, jeu, question, reference, note
    ("agr_churn", "agregat", "telco_churn",
     "Quel est le taux de résiliation global des clients ?", _ref_taux_global, ""),
    ("agr_ca_profit", "agregat", "superstore",
     "Quel est le chiffre d'affaires total et le profit total sur l'ensemble des commandes ?",
     _ref_ca_profit, ""),
    ("agr_revenu", "agregat", "personality",
     "Quel est le revenu annuel moyen des clients ?", _ref_revenu,
     "24 revenus manquants, ignorés dans la moyenne"),
    ("agr_facture", "agregat", "telco_churn",
     "Quelle est la facture mensuelle moyenne d'un client ?", _ref_facture, ""),
    ("cmp_contrat", "comparaison", "telco_churn",
     "Le taux de résiliation varie-t-il selon le type de contrat ?", _ref_contrat, ""),
    ("cmp_seniors", "comparaison", "telco_churn",
     "Les clients seniors résilient-ils davantage que les autres ?", _ref_seniors, ""),
    ("cmp_enfants", "comparaison", "personality",
     "Les clients qui ont des enfants ou des adolescents au foyer dépensent-ils moins que les "
     "autres, toutes catégories de produits confondues ?", _ref_enfants,
     "dépense = somme des six colonnes Mnt*"),
    ("cmp_segment", "comparaison", "superstore",
     "Quel segment de clientèle génère le plus de chiffre d'affaires ?", _ref_segment, ""),
    ("tmp_ca_annuel", "temporel", "superstore",
     "Comment le chiffre d'affaires a-t-il évolué d'une année à l'autre de 2009 à 2012 ?",
     _ref_ca_annuel, ""),
    ("tmp_profit", "temporel", "superstore",
     "Le profit de 2012 est-il supérieur à celui de 2011 ?", _ref_profit_2011_2012, ""),
    ("tmp_recrutement", "temporel", "personality",
     "Combien de nouveaux clients ont été enregistrés chaque année ?", _ref_recrutement,
     "année d'inscription = Dt_Customer"),
    ("tmp_commandes", "temporel", "superstore",
     "Quelle année a connu le plus grand nombre de commandes ?", _ref_commandes,
     "une commande = un Order ID distinct"),
    ("rel_anciennete", "relation", "telco_churn",
     "Les clients qui résilient ont-ils une ancienneté plus faible que ceux qui restent ?",
     _ref_anciennete, ""),
    ("rel_revenu_vin", "relation", "personality",
     "Quelle est la corrélation entre le revenu et les dépenses en vin ?", _ref_revenu_vin,
     "corrélation de Pearson"),
    ("rel_remise_profit", "relation", "superstore",
     "Quelle est la corrélation entre la remise accordée et le profit d'une commande ?",
     _ref_remise_profit, "corrélation de Pearson, ligne à ligne"),
    ("rel_facture", "relation", "telco_churn",
     "La facture mensuelle est-elle plus élevée chez les clients qui partent ?",
     _ref_facture_churn, ""),
    ("cls_sous_categories", "classement", "superstore",
     "Quelles sont les trois sous-catégories de produits les plus rentables ?",
     _ref_top_sous_categories, "rentabilité = profit total"),
    ("cls_region", "classement", "superstore",
     "Quelle région réalise le plus de ventes ?", _ref_region, ""),
    ("cls_depense", "classement", "personality",
     "Sur quelle catégorie de produits les clients dépensent-ils le plus au total ?",
     _ref_depense_categorie, ""),
    ("cls_paiement", "classement", "telco_churn",
     "Quel moyen de paiement présente le taux de résiliation le plus élevé ?", _ref_paiement, ""),
    ("hors_appels", "hors_perimetre", "telco_churn",
     "Combien d'appels au service client un client passe-t-il en moyenne avant de résilier ?",
     _abstain, "aucune colonne d'appels"),
    ("hors_satisfaction", "hors_perimetre", "superstore",
     "Quelle est la note de satisfaction moyenne des clients par région ?", _abstain,
     "aucune colonne de satisfaction"),
    ("hors_paris", "hors_perimetre", "personality",
     "Combien de clients habitent à Paris ?", _abstain, "aucune donnée de localisation"),
    ("hors_2015", "hors_perimetre", "superstore",
     "Quel chiffre d'affaires a été réalisé en 2015 ?", _abstain,
     "les commandes s'arrêtent fin 2012"),
]  # fmt: skip


def build(data_dir: Path, csv_for: Callable[[str], Path | None]) -> list[GoldenCase]:
    """Calcule les faits attendus de chaque question sur les vrais CSV."""
    frames: dict[str, pd.DataFrame] = {}
    cases = []
    for case_id, category, dataset, question, reference, note in QUESTIONS:
        if dataset not in frames:
            path = csv_for(dataset)
            if path is None:
                raise FileNotFoundError(f"Jeu '{dataset}' absent de {data_dir}")
            frames[dataset] = load_frame(path)
        facts = reference(frames[dataset])
        cases.append(GoldenCase(case_id, category, dataset, question, facts, note))
    return cases


# --------------------------------------------------------------------------- serialisation


def dump(cases: list[GoldenCase], path: Path) -> None:
    payload = [
        {**asdict(c), "reference_answer": c.reference_answer, "facts": [asdict(f) for f in c.facts]}
        for c in cases
    ]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def load(path: Path) -> list[GoldenCase]:
    cases = []
    for raw in json.loads(path.read_text()):
        facts = [Fact(**{**f, "aliases": tuple(f.get("aliases", ()))}) for f in raw["facts"]]
        cases.append(
            GoldenCase(
                id=raw["id"],
                category=raw["category"],
                dataset=raw["dataset"],
                question=raw["question"],
                facts=facts,
                note=raw.get("note", ""),
            )
        )
    return cases
