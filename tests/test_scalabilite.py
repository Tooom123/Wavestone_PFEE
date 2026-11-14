"""Gros fichiers : profilage DuckDB sans chargement, consigne au generateur de code."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_data.executor.executor import build_prompt
from agent_data.profiling import profile_csv, profiler
from agent_data.sandbox import MountedDataset
from agent_data.schemas import AnalysisPlan, ColumnKind


def test_duckdb_et_pandas_donnent_le_meme_profil(csv_ventes: Path) -> None:
    a = profile_csv(csv_ventes, engine="pandas")
    b = profile_csv(csv_ventes, engine="duckdb")
    assert a.row_count == b.row_count == 4
    for ca, cb in zip(a.columns, b.columns, strict=True):
        assert (ca.name, ca.kind, ca.null_count, ca.date_range) == (
            cb.name,
            cb.kind,
            cb.null_count,
            cb.date_range,
        )
    montant = b.column("montant")
    assert montant is not None and montant.stats is not None and montant.stats.mean == 175.0
    assert b.profiling.startswith("DuckDB") and a.profiling.startswith("pandas")


def test_bascule_automatique_au_dela_du_seuil(csv_ventes: Path, monkeypatch) -> None:
    monkeypatch.setattr(profiler, "LARGE_FILE_MB", 0)
    assert profile_csv(csv_ventes).profiling.startswith("DuckDB")


def test_fichier_aux_fins_de_ligne_cr(tmp_path: Path) -> None:
    """Le CSV Superstore d'origine utilise des fins de ligne CR seules."""
    path = tmp_path / "cr.csv"
    path.write_bytes(b"Order Date,Sales\r10/13/2010,261.54\r10/1/2012,10123.02\r")
    profile = profile_csv(path, engine="duckdb")
    assert profile.row_count == 2
    date = profile.column("Order Date")
    assert date is not None and date.date_range == ("2010-10-13", "2012-10-01")


def test_oui_non_reste_du_texte(tmp_path: Path) -> None:
    """Le code de l'agent lit avec pandas, qui voit « Yes » : le profil doit le dire."""
    path = tmp_path / "churn.csv"
    path.write_text("Churn,tenure\nYes,1\nNo,30\nNo,12\n")
    churn = profile_csv(path, engine="duckdb").column("Churn")
    assert churn is not None and churn.kind is ColumnKind.CATEGORICAL
    assert set(churn.top_values) == {"Yes", "No"}


def _prompt(csv: Path, size_mb: float) -> str:
    profile = profile_csv(csv).model_copy(update={"size_mb": size_mb})
    plan = AnalysisPlan.model_validate(
        {
            "question": "q",
            "restated_question": "q",
            "steps": [{"id": "s1", "goal": "g", "method": "m"}],
        }  # fmt: skip
    )
    return build_prompt(plan, [profile], [MountedDataset(profile.name, csv)])


def test_consigne_gros_fichier(csv_ventes: Path) -> None:
    prompt = _prompt(csv_ventes, 1000)
    assert "Fichiers volumineux" in prompt and "read_csv('/workspace/data/ventes.csv'" in prompt
    assert "4 lignes, 1000 Mo" in prompt


@pytest.mark.parametrize("size_mb", [0.0, 50.0])
def test_pas_de_consigne_pour_un_petit_fichier(csv_ventes: Path, size_mb: float) -> None:
    assert "Fichiers volumineux" not in _prompt(csv_ventes, size_mb)
