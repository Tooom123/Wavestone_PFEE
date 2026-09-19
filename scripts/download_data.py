"""Telecharge les jeux de donnees de travail dans `data/`.

Les CSV ne sont jamais versionnes : ce script est le moyen de reconstituer `data/` a
l'identique sur n'importe quel poste.

Le registre `DATASETS` est volontairement vide au demarrage : le choix des 3 a 4 datasets
(riches en donnees et techniquement simples) n'est pas arrete. Ajouter une entree par
dataset retenu, puis lancer :

    uv run python scripts/download_data.py            # tous les datasets
    uv run python scripts/download_data.py ventes     # un seul
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@dataclass(frozen=True)
class Dataset:
    """Un jeu de donnees telechargeable depuis une URL directe."""

    name: str
    url: str
    filename: str
    description: str = ""

    @property
    def target(self) -> Path:
        return DATA_DIR / self.name / self.filename


# Exemple de la forme attendue, a remplacer par les datasets retenus :
#
#     Dataset(
#         name="ventes",
#         url="https://exemple.org/ventes.csv",
#         filename="ventes.csv",
#         description="Ventes par modele et par mois",
#     ),
DATASETS: list[Dataset] = []


def download(dataset: Dataset, *, force: bool = False) -> Path:
    """Telecharge `dataset` s'il est absent. Retourne le chemin local du CSV."""
    target = dataset.target
    if target.exists() and not force:
        print(f"[=] {dataset.name} : deja present ({target})")
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"[>] {dataset.name} : telechargement depuis {dataset.url}")
    # Ecriture via un fichier temporaire : un telechargement interrompu ne laisse pas
    # un CSV tronque que le profilage prendrait pour valide.
    tmp = target.with_suffix(target.suffix + ".part")
    try:
        urllib.request.urlretrieve(dataset.url, tmp)  # noqa: S310
        tmp.replace(target)
    finally:
        tmp.unlink(missing_ok=True)
    print(f"[ok] {dataset.name} -> {target}")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("names", nargs="*", help="Datasets a telecharger (defaut : tous)")
    parser.add_argument("--force", action="store_true", help="Retelecharge meme si present")
    args = parser.parse_args(argv)

    if not DATASETS:
        print(
            "Aucun dataset enregistre. Completer la liste DATASETS dans "
            "scripts/download_data.py avec les jeux de donnees retenus.",
            file=sys.stderr,
        )
        return 1

    selection = DATASETS
    if args.names:
        par_nom = {d.name: d for d in DATASETS}
        inconnus = sorted(set(args.names) - par_nom.keys())
        if inconnus:
            connus = ", ".join(sorted(par_nom)) or "(aucun)"
            print(
                f"Dataset inconnu : {', '.join(inconnus)}. Disponibles : {connus}",
                file=sys.stderr,
            )
            return 1
        selection = [par_nom[n] for n in args.names]

    for dataset in selection:
        download(dataset, force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
