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

   Deux chemins de retour ont ete fermes, car un run reel les a empruntes :
   - les **traces d'erreur** reparties vers le modele a l'iteration suivante — pandas y
     recopie la valeur fautive (`could not convert string to float: '7590-VHVEG'`) ;
   - les **artefacts** relus par l'etage 2 — un scoring par client embarque naturellement
     une colonne d'identifiants.

   Dans les deux cas la valeur est masquee avant d'atteindre le modele, tandis que
   l'artefact stocke conserve tout : le rapport affiche le score par client, la synthese
   decrit la tendance sans pouvoir nommer personne.
2. **Code-as-action.** L'agent ecrit du pandas/scikit-learn reellement execute, plutot que
   d'appeler des fonctions predefinies — ce qui garde l'espace d'analyse ouvert. Contrepartie
   obligatoire : le **sandbox**.
3. **Contrat d'artefacts JSON entre les deux etages.** Streamlit et le rapport Word/PDF sont
   deux *renderers* du meme JSON ; le format de sortie peut etre tranche plus tard.

### Le sandbox

Le code genere par le LLM ne s'execute **jamais** sur la machine hote. Il tourne dans un
conteneur jetable : reseau coupe (`--network none`), racine en lecture seule, CSV montes en
lecture seule, capacites Linux retirees, utilisateur non privilegie, quotas memoire/CPU et
timeout. Seul `/workspace/out` est accessible en ecriture.

Si Docker est indisponible, l'agent **refuse d'executer** : il n'existe aucun repli sur
l'hote, et il ne faut pas en ajouter. Ces garanties sont couvertes par des tests
(`tests/test_sandbox.py`) qui verifient reellement que le reseau est injoignable, qu'une
boucle infinie est tuee et qu'une ecriture hors zone de sortie echoue.

## Stack

uv · LangGraph · Ollama (LLM local) · pandas + Pandera · Docker (sandbox) · DuckDB ·
SciPy · scikit-learn · Plotly · Streamlit · Langfuse · ruff + pytest

### Le modele tourne en local

Le projet fonctionne par defaut avec **qwen2.5-coder:14b** servi par Ollama. Rien ne sort
du poste : ni les donnees, ni meme leur profil.

| Critere | Choix retenu |
|---|---|
| Modele | `qwen2.5-coder:14b` (~9 Go, quantisation Q4_K_M) |
| Empreinte GPU | ~9,7 Go de VRAM — tient entierement sur une carte 12 Go |
| Pourquoi celui-la | Meilleur rapport qualite/VRAM en generation de code a cette taille |
| Alternative poste modeste | `qwen2.5-coder:7b` (~4,7 Go) : `LLM_MODEL=qwen2.5-coder:7b` |

`qwen3-coder:30b` a ete ecarte : 18,6 Go, il deborde une carte 12 Go et bascule sur le CPU.
Basculer vers une API distante ne demande que de changer `LLM_PROVIDER` dans `.env` — la
decision reste ouverte cote Wavestone.

## Demarrage

Un seul script installe tout (uv, dependances, Ollama et son modele, image du sandbox,
jeux de donnees) :

```bash
git clone <repo> && cd Wavestone_PFEE
./scripts/setup.sh
```

Options utiles : `--skip-model` (ne telecharge pas les ~9 Go du modele), `--skip-data`,
`--skip-docker`. Le script est idempotent : on peut le relancer sans risque.

Verifier que tout est en place :

```bash
uv run agent-data check
```

### Utilisation

```bash
# Poser une question sur un jeu de donnees
uv run agent-data ask "Quelles categories tirent la marge vers le bas ?" \
    -d data/superstore/superstore.csv

# Voir le profil d'un CSV : exactement ce que recoit le LLM
uv run agent-data profile data/telco_churn/telco_churn.csv

# Interface graphique
uv run streamlit run src/agent_data/ui/app.py
```

Qualite :

```bash
uv run ruff check .
uv run pytest          # les tests du sandbox exigent Docker, sinon ils sont ignores
```

## Structure

```
src/agent_data/
  profiling/       profilage des CSV -> DatasetProfile (seul objet envoye au LLM)
  planner/         question metier + profil -> plan d'analyse
  executor/        plan -> code Python
  sandbox/         execution isolee du code genere (Docker)
  critic/          relecture des resultats, correction, relance
  rendering/       etage 2 : artefacts JSON -> synthese et rapport
  llm/             acces au modele (Ollama par defaut)
  eval/            evaluation separee des deux etages
  ui/app.py        interface Streamlit
  graph.py         boucle agentique de l'etage 1
  pipeline.py      enchainement des deux etages
  schemas.py       modeles Pydantic (contrats entre etages)
  config.py        configuration lue depuis .env
docker/            image du sandbox et helpers injectes dedans
data/              jeux de donnees locaux (non versionnes)
scripts/           setup.sh (installation) et download_data.py
tests/
```

## Evaluation

Les deux etages sont evalues separement — c'est tout l'interet du decoupage demande par
Wavestone. Un cas par famille d'analyse :

```bash
uv run python scripts/run_eval.py                      # les trois cas
uv run python scripts/run_eval.py --case ventes_qualite
uv run python scripts/run_eval.py --stage 1            # etage 1 uniquement
```

Chaque cas declenche un run reel (LLM local + sandbox) : compter une a trois minutes par
cas, davantage pour ceux qui impliquent du ML.

Derniere execution complete : **24/24 controles reussis**.

| Cas | Famille | Duree | Iterations | Artefacts |
|---|---|---|---|---|
| `churn_facteurs` | ML supervise | 134 s | 5 | 4 |
| `ventes_qualite` | BI descriptive | 53 s | 1 | 5 |
| `segments_clients` | Clustering | 103 s | 4 | 10 |

Le nombre d'iterations varie d'un run a l'autre : la generation de code n'est pas
deterministe, meme a temperature 0 (le plan, lui, l'est). Juger sur plusieurs runs.

## Jeux de donnees

Trois jeux couvrent les trois familles d'analyse du perimetre. `./scripts/setup.sh` les
telecharge ; `uv run python scripts/download_data.py` aussi.

| Dataset | Taille | Famille | Ce qu'il demontre |
|---|---|---|---|
| `telco_churn` | 7 043 x 21 | ML supervise | Classification sur une cible claire (`Churn`), facteurs de depart |
| `superstore` | 8 399 x 21 | BI descriptive | Temps, geographie, categories, marge — le cas d'usage cite par Wavestone |
| `personality` | 2 240 x 29 | Exploration | Segmentation et RFM, sans cible predefinie |

## Conventions

- **uv** partout, jamais de `pip install` direct. `pyproject.toml` et `uv.lock` versionnes.
- Branches : `main` (protegee) et `dev`. Toute feature -> branche -> PR vers `dev`.
- CI sur chaque PR : `uv sync` -> `ruff check` -> `pytest`.
- **Aucun CSV brut versionne.** Aucune cle API dans le depot.
