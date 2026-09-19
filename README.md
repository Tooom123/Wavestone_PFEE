# Agent Data

Systeme d'**IA agentique pour l'analyse de donnees**. Entree : une **question metier en
langage naturel** posee par un decideur, et un ou plusieurs **jeux de donnees CSV**.
Sortie : une **reponse analytique** (statistiques, ML, restitution) obtenue en suivant une
demarche d'analyse decidee par l'agent — sans intervention technique de l'utilisateur.

C'est un **agent, pas un pipeline** : la demarche d'analyse est choisie en fonction de la
question, avec une boucle de critique et de correction.

Projet de fin d'etudes EPITA, en partenariat avec Wavestone.

## Architecture

```
Question metier ─┐
                 ├─► Profilage ─► ETAGE 1 ─► Artefacts JSON ─► ETAGE 2 ─► Restitution
CSV ─────────────┘   (metadonnees)  (boucle)    (contrat)                 (Streamlit / Word-PDF)
```

- **Etage 1** — boucle agentique LangGraph : planificateur -> executeur (generation de code)
  -> sandbox Docker -> critique, avec etat partage et plafond d'iterations.
- **Etage 2** — restitution : artefacts JSON -> synthese en langage naturel -> renderer.

Les deux etages sont testables et evaluables independamment.

### Partis pris

1. **Le LLM ne voit jamais les donnees brutes.** Seul le *profil* du dataset (schema, types,
   cardinalites, taux de nulls, stats descriptives) entre dans son contexte. Le code
   s'execute sur les donnees, le LLM raisonne sur les metadonnees.
2. **Code-as-action.** L'agent ecrit du pandas/scikit-learn reellement execute, plutot que
   d'appeler des fonctions predefinies — ce qui garde l'espace d'analyse ouvert. Contrepartie
   obligatoire : le **sandbox**.
3. **Contrat d'artefacts JSON entre les deux etages.** Streamlit et le rapport Word/PDF sont
   deux *renderers* du meme JSON ; le format de sortie peut etre tranche plus tard.

## Stack

uv · LangGraph · pandas + Pandera · Docker (sandbox) · DuckDB · SciPy · scikit-learn ·
Plotly · Streamlit · Langfuse · ruff + pytest

## Demarrage

Prerequis : [uv](https://docs.astral.sh/uv/) et Docker.

```bash
uv sync                  # installe les dependances
cp .env.example .env     # puis renseigner les cles API
uv run agent-data        # point d'entree CLI
```

Qualite :

```bash
uv run ruff check .
uv run pytest
```

## Structure

```
src/agent_data/
  profiling/   profilage des CSV -> DatasetProfile (seul objet envoye au LLM)
  planner/     question metier + profil -> plan d'analyse
  executor/    plan -> code Python
  sandbox/     execution isolee du code genere (Docker)
  critic/      relecture des resultats, correction, relance
  rendering/   artefacts JSON -> restitution
  graph.py     graphe LangGraph de l'etage 1
  schemas.py   modeles Pydantic (contrats entre etages)
data/          jeux de donnees locaux (non versionnes)
scripts/       utilitaires (telechargement des datasets)
tests/
```

## Conventions

- **uv** partout, jamais de `pip install` direct. `pyproject.toml` et `uv.lock` versionnes.
- Branches : `main` (protegee) et `dev`. Toute feature -> branche -> PR vers `dev`.
- CI sur chaque PR : `uv sync` -> `ruff check` -> `pytest`.
- **Aucun CSV brut versionne.** Aucune cle API dans le depot.
