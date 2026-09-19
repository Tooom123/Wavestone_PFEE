"""Telecharge les jeux de donnees de travail dans `data/`.

Les CSV ne sont jamais versionnes : ce script est le moyen de reconstituer `data/` a
l'identique sur n'importe quel poste.

Le trio couvre les trois familles du perimetre de l'agent :
  - telco_churn  : ML supervise (classification) — une cible claire, `Churn`.
  - superstore   : BI descriptive — temps, geographie, categories, marge.
  - personality  : exploration non supervisee — segmentation, RFM, correlations.

Usage :
    uv run python scripts/download_data.py            # tous les datasets
    uv run python scripts/download_data.py superstore # un seul
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

USER_AGENT = "agent-data/0.1 (projet PFEE Wavestone)"


@dataclass(frozen=True)
class Dataset:
    """Un jeu de donnees telechargeable depuis une URL directe."""

    name: str
    url: str
    filename: str
    description: str = ""
    encoding: str | None = None
    """Encodage source, si le fichier n'est pas en UTF-8. Il est alors reencode."""

    @property
    def target(self) -> Path:
        return DATA_DIR / self.name / self.filename


DATASETS: list[Dataset] = [
    Dataset(
        name="telco_churn",
        url=(
            "https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d/"
            "master/data/Telco-Customer-Churn.csv"
        ),
        filename="telco_churn.csv",
        description=(
            "Telco Customer Churn (IBM) — 7043 clients, 21 colonnes, cible 'Churn'. "
            "Ancre machine learning : classification, facteurs de depart, segments a risque."
        ),
    ),
    Dataset(
        name="superstore",
        url=(
            "https://raw.githubusercontent.com/curran/data/"
            "gh-pages/superstoreSales/superstoreSales.csv"
        ),
        filename="superstore.csv",
        description=(
            "Superstore Sales — 8399 commandes 2009-2012, 21 colonnes. Ancre analyse de "
            "ventes : dates, regions, categories, marges. Proche du cas d'usage cite par "
            "Wavestone (comparer la qualite des ventes d'un produit)."
        ),
        # Le fichier source est en latin-1 : sans reencodage, pandas echoue a le lire.
        encoding="latin-1",
    ),
    Dataset(
        name="personality",
        url=(
            "https://raw.githubusercontent.com/nailson/ifood-data-business-analyst-test/"
            "master/ml_project1_data.csv"
        ),
        filename="customer_personality.csv",
        description=(
            "Customer Personality Analysis — 2240 clients, 29 colonnes (demographie, "
            "depenses par categorie, campagnes). Ancre exploration : clustering, RFM."
        ),
    ),
]


def download(dataset: Dataset, *, force: bool = False) -> Path:
    """Telecharge `dataset` s'il est absent. Retourne le chemin local du CSV."""
    target = dataset.target
    if target.exists() and not force:
        print(f"[=] {dataset.name} : deja present ({target})")
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"[>] {dataset.name} : telechargement…")
    # Ecriture via un fichier temporaire : un telechargement interrompu ne laisse pas
    # un CSV tronque que le profilage prendrait pour valide.
    tmp = target.with_suffix(target.suffix + ".part")
    try:
        request = urllib.request.Request(dataset.url, headers={"User-Agent": USER_AGENT})  # noqa: S310
        with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
            payload = response.read()
        if dataset.encoding:
            # Normalisation en UTF-8 : tout le reste du projet lit de l'UTF-8.
            payload = payload.decode(dataset.encoding).encode("utf-8")
        tmp.write_bytes(payload)
        tmp.replace(target)
    finally:
        tmp.unlink(missing_ok=True)

    size = target.stat().st_size / 1024
    print(f"[ok] {dataset.name} -> {target} ({size:.0f} Ko)")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Telecharge les jeux de donnees du projet.")
    parser.add_argument("names", nargs="*", help="Datasets a telecharger (defaut : tous)")
    parser.add_argument("--force", action="store_true", help="Retelecharge meme si present")
    parser.add_argument("--list", action="store_true", help="Liste les datasets disponibles")
    args = parser.parse_args(argv)

    if args.list:
        for d in DATASETS:
            print(f"{d.name:14} {d.description}")
        return 0

    selection = DATASETS
    if args.names:
        par_nom = {d.name: d for d in DATASETS}
        inconnus = sorted(set(args.names) - par_nom.keys())
        if inconnus:
            print(
                f"Dataset inconnu : {', '.join(inconnus)}. "
                f"Disponibles : {', '.join(sorted(par_nom))}",
                file=sys.stderr,
            )
            return 1
        selection = [par_nom[n] for n in args.names]

    failures = 0
    for dataset in selection:
        try:
            download(dataset, force=args.force)
        except (OSError, UnicodeDecodeError) as exc:
            print(f"[!] {dataset.name} : echec ({exc})", file=sys.stderr)
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
