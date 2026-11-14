"""Mesure le passage a l'echelle : profilage et agregation sur des CSV de taille croissante.

    uv run python scripts/bench_scale.py                    # 0,25 et 1 Go (disque : ~1,3 Go)
    uv run python scripts/bench_scale.py --sizes 0.1 0.5 2 --keep

Les fichiers sont fabriques en repetant `data/superstore` (identifiants decales). Chaque
mesure tourne dans un processus a part, pour lire sa memoire maximale (RSS) sans qu'une
mesure precedente la fausse. Resultat : docs/scalabilite-mesures.json.

Mesures :
  - profilage pandas (lecture complete) et DuckDB (`profile_large_csv`) ;
  - le calcul type de l'agent (chiffre d'affaires par annee) ecrit de trois facons :
    pandas sur tout le fichier, pandas sur les seules colonnes utiles (`usecols`), et DuckDB
    limite a 2 coeurs comme dans le sandbox.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess  # nosec B404 - interpreteur courant, arguments fixes
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data/superstore/superstore.csv"
OUT = ROOT / "docs/scalabilite-mesures.json"
SANDBOX_MEMORY_MB = 2048

TASKS = {
    "profil_pandas": """
from agent_data.profiling import profile_csv
p = profile_csv(PATH, engine="pandas"); RESULT = p.row_count
""",
    "profil_duckdb": """
from agent_data.profiling import profile_csv
p = profile_csv(PATH, engine="duckdb"); RESULT = p.row_count
""",
    "agregat_pandas_complet": """
import pandas as pd
df = pd.read_csv(PATH)
df["Order Date"] = pd.to_datetime(df["Order Date"])
RESULT = float(df.groupby(df["Order Date"].dt.year)["Sales"].sum().iloc[-1])
""",
    "agregat_pandas_usecols": """
import pandas as pd
df = pd.read_csv(PATH, usecols=["Order Date", "Sales"])
df["Order Date"] = pd.to_datetime(df["Order Date"])
RESULT = float(df.groupby(df["Order Date"].dt.year)["Sales"].sum().iloc[-1])
""",
    "demarrage_python": """
RESULT = 0
""",
    "agregat_duckdb_2_coeurs": """
import duckdb
con = duckdb.connect(); con.execute("SET threads = 2")
q = (f"SELECT year(\\"Order Date\\") AS an, sum(Sales) FROM read_csv('{PATH}') "
     "GROUP BY an ORDER BY an")
RESULT = float(con.sql(q).fetchall()[-1][1])
""",
}

PARQUET_TASK = TASKS["agregat_duckdb_2_coeurs"].replace("read_csv(", "read_parquet(")


def make_csv(target_gb: float, path: Path) -> int:
    """Repete le jeu source jusqu'a la taille visee ; rend le nombre de lignes."""
    import pandas as pd

    base = pd.read_csv(SOURCE)
    base["Order Date"] = pd.to_datetime(base["Order Date"]).dt.strftime("%Y-%m-%d")
    rows, first = 0, True
    with path.open("w", encoding="utf-8") as fh:
        k = 0
        while fh.tell() < target_gb * 1e9:
            chunk = base.copy()
            chunk["Row ID"] += k * len(base)
            chunk["Order ID"] += k * 100_000
            chunk.to_csv(fh, index=False, header=first)
            rows += len(chunk)
            first, k = False, k + 1
    return rows


def make_csv_apart(target_gb: float, path: Path) -> int:
    """`make_csv` dans un processus a part.

    Le parent doit rester leger : sous Linux, un processus lance par fork herite de la
    memoire de son parent dans sa mesure de pic (ru_maxrss). Un parent qui aurait charge
    pandas fausserait toutes les mesures qui suivent.
    """
    code = (
        "import sys; sys.path.insert(0, 'scripts'); from bench_scale import make_csv; "
        f"print(make_csv({target_gb!r}, __import__('pathlib').Path({str(path)!r})))"
    )
    out = subprocess.run(  # nosec B603 - interpreteur courant, code du depot
        [sys.executable, "-c", code], cwd=ROOT, check=True, capture_output=True, text=True
    )
    return int(out.stdout.strip())


def measure(task: str, path: Path) -> dict:
    """Execute une tache dans un processus neuf ; rend sa duree et sa memoire maximale."""
    code = f"PATH = {str(path)!r}\n{TASKS[task]}\nprint(RESULT)"
    started = time.monotonic()
    proc = subprocess.Popen(  # nosec B603 - interpreteur courant, code du depot
        [sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=ROOT
    )
    _, status, usage = os.wait4(proc.pid, 0)
    seconds = time.monotonic() - started
    out = proc.stdout.read().decode().strip() if proc.stdout else ""
    err = proc.stderr.read().decode().strip()[-300:] if proc.stderr else ""
    peak_mb = usage.ru_maxrss / 1024  # Linux : kilo-octets
    return {
        "task": task,
        "seconds": round(seconds, 2),
        "peak_mb": round(peak_mb),
        "fits_sandbox": peak_mb < SANDBOX_MEMORY_MB,
        "ok": status == 0,
        "result": out[-40:],
        "error": "" if status == 0 else err,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=float, nargs="+", default=[0.25, 1.0], help="En Go")
    parser.add_argument("--workdir", default=str(ROOT / ".agent_data" / "bench"))
    parser.add_argument("--keep", action="store_true", help="Garde les CSV generes")
    args = parser.parse_args(argv)

    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    results = []
    for size in args.sizes:
        path = workdir / f"superstore_{size:g}go.csv"
        rows = make_csv_apart(size, path)
        real_gb = path.stat().st_size / 1e9
        print(f"\n== {real_gb:.2f} Go, {rows:,} lignes".replace(",", " "), flush=True)
        for task in TASKS:
            m = measure(task, path) | {"size_gb": round(real_gb, 2), "rows": rows}
            flag = "" if m["ok"] else f" ECHEC {m['error'][-80:]}"
            sandbox = "tient" if m["fits_sandbox"] else "DEPASSE"
            print(f"   {task:<26} {m['seconds']:>7.1f} s  {m['peak_mb']:>6} Mo  "
                  f"(sandbox 2 Go : {sandbox}){flag}", flush=True)  # fmt: skip
            results.append(m)
        parquet = path.with_suffix(".parquet")
        subprocess.run(  # nosec B603 - interpreteur courant, code du depot
            [sys.executable, "-c", "import duckdb; duckdb.sql(\"COPY (SELECT * FROM "
             f"read_csv('{path}')) TO '{parquet}' (FORMAT parquet)\")"],
            cwd=ROOT, check=True,
        )  # fmt: skip
        TASKS["agregat_duckdb_parquet_2_coeurs"] = PARQUET_TASK
        m = measure("agregat_duckdb_parquet_2_coeurs", parquet) | {
            "size_gb": round(parquet.stat().st_size / 1e9, 3),
            "rows": rows,
            "csv_size_gb": round(real_gb, 2),
        }
        del TASKS["agregat_duckdb_parquet_2_coeurs"]
        print(f"   parquet ({m['size_gb']} Go)           {m['seconds']:>7.2f} s  "
              f"{m['peak_mb']:>6} Mo", flush=True)  # fmt: skip
        results.append(m)
        parquet.unlink()
        if not args.keep:
            path.unlink()

    OUT.write_text(json.dumps({"cpu": os.cpu_count(), "results": results}, indent=2) + "\n")
    print(f"\nMesures ecrites dans {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
