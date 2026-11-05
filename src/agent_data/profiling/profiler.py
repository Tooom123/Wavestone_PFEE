"""Profilage d'un CSV vers un :class:`DatasetProfile`.

Ce module materialise le parti pris central du projet : **le LLM ne voit jamais les
donnees brutes**. La sortie ne contient que des metadonnees et des statistiques agregees.
La seule exception controlee est `top_values` (modalites les plus frequentes d'une colonne
categorielle), indispensable pour que le planificateur sache sur quoi filtrer ; elle est
plafonnee et desactivable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from agent_data.schemas import (
    ColumnKind,
    ColumnProfile,
    DatasetProfile,
    NumericStats,
)

MAX_TOP_VALUES = 10
"""Nombre maximum de modalites remontees par colonne categorielle."""

CATEGORICAL_MAX_UNIQUE = 50
"""Au-dela de ce nombre de modalites, une colonne texte est traitee comme du texte libre."""


def _infer_kind(series: pd.Series) -> ColumnKind:
    """Deduit la nature d'une colonne a partir de son dtype et de sa cardinalite."""
    if pd.api.types.is_bool_dtype(series):
        return ColumnKind.BOOLEAN
    if pd.api.types.is_numeric_dtype(series):
        return ColumnKind.NUMERIC
    if pd.api.types.is_datetime64_any_dtype(series):
        return ColumnKind.DATETIME
    # Objet ou chaine : categoriel si peu de modalites distinctes, sinon texte libre.
    if series.nunique(dropna=True) <= CATEGORICAL_MAX_UNIQUE:
        return ColumnKind.CATEGORICAL
    return ColumnKind.TEXT


def _numeric_stats(series: pd.Series) -> NumericStats:
    """Statistiques descriptives d'une colonne numerique, NaN convertis en None."""
    clean = series.dropna()
    if clean.empty:
        return NumericStats()

    def _f(value: object) -> float | None:
        try:
            out = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None
        return None if pd.isna(out) else out

    return NumericStats(
        min=_f(clean.min()),
        max=_f(clean.max()),
        mean=_f(clean.mean()),
        std=_f(clean.std()) if len(clean) > 1 else 0.0,
        p25=_f(clean.quantile(0.25)),
        median=_f(clean.median()),
        p75=_f(clean.quantile(0.75)),
    )


def profile_column(series: pd.Series, *, include_top_values: bool = True) -> ColumnProfile:
    """Profile une colonne unique."""
    kind = _infer_kind(series)
    null_count = int(series.isna().sum())
    total = len(series)

    stats = _numeric_stats(series) if kind is ColumnKind.NUMERIC else None

    top_values: list[str] = []
    if include_top_values and kind in (ColumnKind.CATEGORICAL, ColumnKind.BOOLEAN):
        counts = series.value_counts(dropna=True).head(MAX_TOP_VALUES)
        top_values = [str(v) for v in counts.index]

    return ColumnProfile(
        name=str(series.name),
        kind=kind,
        dtype=str(series.dtype),
        null_count=null_count,
        null_ratio=(null_count / total) if total else 0.0,
        unique_count=int(series.nunique(dropna=True)),
        stats=stats,
        top_values=top_values,
    )


def profile_dataframe(
    df: pd.DataFrame,
    *,
    name: str,
    source_path: str = "",
    include_top_values: bool = True,
) -> DatasetProfile:
    """Profile un DataFrame deja charge."""
    return DatasetProfile(
        name=name,
        source_path=source_path,
        row_count=len(df),
        columns=[
            profile_column(df[col], include_top_values=include_top_values) for col in df.columns
        ],
    )


def profile_csv(
    path: str | Path,
    *,
    name: str | None = None,
    include_top_values: bool = True,
    parse_dates: bool = True,
    **read_csv_kwargs: Any,
) -> DatasetProfile:
    """Charge un CSV et en retourne le profil.

    `parse_dates` tente une conversion des colonnes texte en dates : sans cela, une colonne
    de dates serait profilee comme du texte libre et le planificateur ignorerait qu'une
    analyse temporelle est possible.
    """
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV introuvable : {csv_path}")

    df = pd.read_csv(csv_path, **read_csv_kwargs)
    if parse_dates:
        df = _coerce_dates(df)

    return profile_dataframe(
        df,
        name=name or csv_path.stem,
        source_path=str(csv_path),
        include_top_values=include_top_values,
    )


def _coerce_dates(df: pd.DataFrame, *, min_success_ratio: float = 0.9) -> pd.DataFrame:
    """Convertit en datetime les colonnes texte qui s'y pretent largement."""
    for col in df.columns:
        series = df[col]
        if not (pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)):
            continue
        non_null = series.dropna()
        if non_null.empty:
            continue
        converted = pd.to_datetime(series, errors="coerce", format="mixed")
        success = converted.notna().sum() / len(non_null)
        if success >= min_success_ratio:
            df[col] = converted
    return df
