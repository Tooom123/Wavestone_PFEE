"""Profilage d'un CSV vers un :class:`DatasetProfile`.

Ce module materialise le parti pris central du projet : **le LLM ne voit jamais les
donnees brutes**. La sortie ne contient que des metadonnees et des statistiques agregees.
La seule exception controlee est `top_values` (modalites les plus frequentes d'une colonne
categorielle), indispensable pour que le planificateur sache sur quoi filtrer ; elle est
plafonnee et desactivable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

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

LARGE_FILE_MB = 200
"""Au-dela, le profil est calcule par DuckDB sans charger le fichier (docs/scalabilite.md)."""

SAMPLE_ROWS = 100_000
"""Taille de l'echantillon qui donne la nature des colonnes et leurs modalites."""


def _f(value: object) -> float | None:
    """Flottant ou None (NaN, texte, valeur absente)."""
    try:
        out = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return None if pd.isna(out) else out


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

    date_range = None
    if kind is ColumnKind.DATETIME and series.notna().any():
        date_range = (series.min().date().isoformat(), series.max().date().isoformat())

    return ColumnProfile(
        name=str(series.name),
        kind=kind,
        dtype=str(series.dtype),
        null_count=null_count,
        null_ratio=(null_count / total) if total else 0.0,
        unique_count=int(series.nunique(dropna=True)),
        stats=stats,
        top_values=top_values,
        date_range=date_range,
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
    engine: Literal["auto", "pandas", "duckdb"] = "auto",
    **read_csv_kwargs: Any,
) -> DatasetProfile:
    """Charge un CSV et en retourne le profil.

    Au-dela de `LARGE_FILE_MB`, le profil est calcule par DuckDB sans charger le fichier
    (`profile_large_csv`) : pandas demanderait plusieurs fois la taille du fichier en RAM.

    `parse_dates` tente une conversion des colonnes texte en dates : sans cela, une colonne
    de dates serait profilee comme du texte libre et le planificateur ignorerait qu'une
    analyse temporelle est possible.
    """
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV introuvable : {csv_path}")
    size_mb = csv_path.stat().st_size / 1e6
    if engine == "duckdb" or (engine == "auto" and size_mb >= LARGE_FILE_MB):
        return profile_large_csv(
            csv_path, name=name, include_top_values=include_top_values, size_mb=size_mb
        )

    df = pd.read_csv(csv_path, **read_csv_kwargs)
    if parse_dates:
        df = _coerce_dates(df)

    profile = profile_dataframe(
        df,
        name=name or csv_path.stem,
        source_path=str(csv_path),
        include_top_values=include_top_values,
    )
    return profile.model_copy(update={"size_mb": round(size_mb, 1)})


def profile_large_csv(
    path: Path,
    *,
    name: str | None = None,
    include_top_values: bool = True,
    size_mb: float | None = None,
    sample_rows: int = SAMPLE_ROWS,
) -> DatasetProfile:
    """Profile un gros CSV sans le charger en memoire.

    DuckDB calcule en une passe parallele, sur tout le fichier, le nombre de lignes, les
    valeurs manquantes, les bornes, moyennes et quantiles, et la periode des dates. La
    nature des colonnes et leurs modalites viennent d'un echantillon aleatoire (reservoir) :
    elles servent a orienter le plan, pas a le chiffrer. Le nombre de valeurs distinctes et
    les quantiles sont des approximations (HyperLogLog, quantiles approches).
    """
    import duckdb

    con = duckdb.connect()
    # Pas de detection des booleens : le code de l'agent lit le fichier avec pandas, qui voit
    # « Yes »/« No » comme du texte. Un profil qui annoncerait un booleen l'induirait en erreur.
    types = ["BIGINT", "DOUBLE", "DATE", "TIMESTAMP", "VARCHAR"]
    try:
        rel = con.read_csv(str(path), auto_type_candidates=types)
        rel.limit(1).fetchall()
    except duckdb.InvalidInputException:
        # Fins de ligne anciennes (CR seul) ou guillemets non conformes : mode tolerant.
        rel = con.read_csv(str(path), auto_type_candidates=types, strict_mode=False)
    summary = {
        row["column_name"]: row
        for row in con.sql("SUMMARIZE SELECT * FROM rel").df().to_dict("records")
    }
    row_count = int(next(iter(summary.values()))["count"]) if summary else 0
    sample = con.sql(
        f"SELECT * FROM rel USING SAMPLE reservoir({int(sample_rows)} ROWS) REPEATABLE (42)"  # nosec B608 - entier
    ).df()
    base = profile_dataframe(
        _coerce_dates(sample),
        name=name or path.stem,
        source_path=str(path),
        include_top_values=include_top_values,
    )
    columns = [_exact(col, summary.get(col.name), row_count) for col in base.columns]
    return base.model_copy(
        update={
            "row_count": row_count,
            "columns": columns,
            "size_mb": round(size_mb if size_mb is not None else path.stat().st_size / 1e6, 1),
            "profiling": (
                f"DuckDB sur les {row_count} lignes ; nature des colonnes et modalites sur un "
                f"echantillon de {min(sample_rows, row_count)} lignes"
            ),
        }
    )


def _exact(col: ColumnProfile, summary: dict | None, row_count: int) -> ColumnProfile:
    """Remplace les statistiques de l'echantillon par celles du fichier complet."""
    if summary is None:
        return col
    null_count = round(row_count * float(summary["null_percentage"] or 0) / 100)
    update: dict[str, Any] = {
        "null_count": null_count,
        "null_ratio": null_count / row_count if row_count else 0.0,
        "unique_count": min(int(summary["approx_unique"] or 0), row_count),
    }
    kind = str(summary["column_type"]).upper()
    if col.kind is ColumnKind.NUMERIC and kind not in ("VARCHAR", "DATE", "TIMESTAMP"):
        update["stats"] = NumericStats(
            min=_f(summary["min"]),
            max=_f(summary["max"]),
            mean=_f(summary["avg"]),
            std=_f(summary["std"]),
            p25=_f(summary["q25"]),
            median=_f(summary["q50"]),
            p75=_f(summary["q75"]),
        )
    if kind.startswith(("DATE", "TIMESTAMP")) and summary["min"] is not None:
        update["date_range"] = (str(summary["min"])[:10], str(summary["max"])[:10])
    return col.model_copy(update=update)


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
