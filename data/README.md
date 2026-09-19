# data/

Repertoire des jeux de donnees locaux. **Aucun CSV n'est versionne** (decision Wavestone) :
`.gitignore` exclut `data/` a l'exception de ce README.

## Recuperer les donnees

```bash
uv run python scripts/download_data.py            # les trois jeux
uv run python scripts/download_data.py superstore # un seul
uv run python scripts/download_data.py --list     # voir ce qui est disponible
```

`./scripts/setup.sh` le fait aussi, avec le reste de l'installation.

## Les trois jeux de donnees

Le trio couvre les trois familles d'analyse du perimetre de l'agent. S'il passe ces trois
cas, il a demontre stats descriptives, ML supervise et exploration non supervisee.

### `telco_churn/` — Telco Customer Churn (IBM)

7 043 lignes x 21 colonnes, aucune valeur manquante. Cible `Churn` (26,5 % de positifs).

L'ancre **machine learning** : classification, analyse des facteurs de depart,
segmentation des clients a risque. C'est le jeu de churn canonique — la question metier
(« quels clients vont partir et pourquoi ») se traduit sans ambiguite.

### `superstore/` — Superstore Sales

8 399 commandes de 2009 a 2012, 21 colonnes. Dates, 8 regions, 3 categories, ventes,
remises et marges dans une table unique.

L'ancre **analyse de ventes**, la plus proche du cas d'usage cite par Wavestone (un
directeur qui veut comparer la qualite des ventes d'un produit). Temps, geographie,
categories et marge suffisent a porter de vraies questions de decideur.

> Le fichier source est encode en latin-1 ; `download_data.py` le reencode en UTF-8.

### `personality/` — Customer Personality Analysis

2 240 clients x 29 colonnes : demographie, depenses par categorie de produit, reponses
aux campagnes. 24 valeurs manquantes sur `Income`.

L'ancre **exploration** : segmentation, RFM, correlations. Il montre que l'agent sait
travailler sans cible predefinie.

## Conventions

- Un sous-dossier par jeu de donnees.
- Les fichiers restent tels que telecharges : la preparation appartient au code genere,
  pas au depot.
