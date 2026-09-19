"""Tests du profilage.

Le test le plus important est :func:`test_profil_ne_contient_aucune_donnee_brute` : il
verifie le parti pris central du projet (le LLM ne voit jamais les donnees).
"""

from __future__ import annotations

import pandas as pd
import pytest

from agent_data.profiling import profile_csv, profile_dataframe
from agent_data.profiling.profiler import CATEGORICAL_MAX_UNIQUE, MAX_TOP_VALUES
from agent_data.schemas import ColumnKind


@pytest.fixture
def df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "montant": [10.0, 20.0, 30.0, None],
            "categorie": ["a", "b", "a", "b"],
            "actif": [True, False, True, True],
            "date": ["2024-01-01", "2024-02-01", "2024-03-01", "2024-04-01"],
        }
    )


def test_types_de_colonnes_deduits(df: pd.DataFrame) -> None:
    profile = profile_dataframe(df, name="t")
    kinds = {c.name: c.kind for c in profile.columns}
    assert kinds["montant"] is ColumnKind.NUMERIC
    assert kinds["categorie"] is ColumnKind.CATEGORICAL
    assert kinds["actif"] is ColumnKind.BOOLEAN


def test_nulls_et_stats(df: pd.DataFrame) -> None:
    montant = profile_dataframe(df, name="t").column("montant")
    assert montant is not None
    assert montant.null_count == 1
    assert montant.null_ratio == pytest.approx(0.25)
    assert montant.stats is not None
    assert montant.stats.mean == pytest.approx(20.0)
    assert montant.stats.median == pytest.approx(20.0)


def test_colonne_entierement_nulle_ne_casse_pas() -> None:
    profile = profile_dataframe(pd.DataFrame({"vide": [None, None]}), name="t")
    col = profile.column("vide")
    assert col is not None
    assert col.null_ratio == 1.0


def test_identifiant_unique_traite_en_texte_sans_valeurs() -> None:
    """Un identifiant ne doit jamais partir dans le contexte du LLM."""
    ids = pd.DataFrame({"id": [f"CLI-{i}" for i in range(CATEGORICAL_MAX_UNIQUE + 10)]})
    col = profile_dataframe(ids, name="t").column("id")
    assert col is not None
    assert col.kind is ColumnKind.TEXT
    assert col.top_values == []


def test_top_values_plafonne() -> None:
    many = pd.DataFrame({"c": [f"v{i % (MAX_TOP_VALUES + 5)}" for i in range(200)]})
    col = profile_dataframe(many, name="t").column("c")
    assert col is not None
    assert len(col.top_values) <= MAX_TOP_VALUES


def test_profil_ne_contient_aucune_donnee_brute() -> None:
    """Parti pris 1 : aucune valeur individuelle ne doit figurer dans le profil."""
    secrets = [f"secret-{i}" for i in range(100)]
    frame = pd.DataFrame({"email": secrets, "montant": range(100)})
    blob = profile_dataframe(frame, name="t").model_dump_json()
    assert not any(s in blob for s in secrets)


def test_dates_detectees(df: pd.DataFrame) -> None:
    frame = df.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    col = profile_dataframe(frame, name="t").column("date")
    assert col is not None
    assert col.kind is ColumnKind.DATETIME


def test_profile_csv_detecte_les_dates_texte(tmp_path) -> None:
    csv = tmp_path / "d.csv"
    csv.write_text("jour,v\n2024-01-01,1\n2024-02-01,2\n2024-03-03,3\n")
    col = profile_csv(csv).column("jour")
    assert col is not None
    assert col.kind is ColumnKind.DATETIME


def test_profile_csv_absent() -> None:
    with pytest.raises(FileNotFoundError):
        profile_csv("/introuvable/nulle-part.csv")


def test_desactivation_des_top_values(df: pd.DataFrame) -> None:
    profile = profile_dataframe(df, name="t", include_top_values=False)
    assert all(c.top_values == [] for c in profile.columns)
