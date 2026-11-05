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

## Demonstration en ligne

L'agent ne peut pas tourner sur Vercel : il lui faut un GPU, Docker et des runs de plusieurs
minutes, quand le serverless n'offre ni l'un ni l'autre. Le montage retenu separe donc
l'interface du cerveau :

```
navigateur ──► front Next.js (Vercel) ──► tunnel HTTPS ──► API FastAPI ──► Ollama + sandbox Docker
                       web/                cloudflared      (ce poste)         (donnees et modeles)
```

Rien d'autre que du texte ne transite par Vercel : les donnees, les modeles et le code genere
restent sur le poste de l'equipe, ce qui preserve l'isolation des donnees. L'API exige un
jeton, ne sert que les jeux de `data/` (jamais un chemin fourni par le client) et n'accepte
qu'un run a la fois, la carte graphique n'en portant pas deux.

```bash
# Poste qui porte l'agent : API + tunnel, affiche le lien a ouvrir
./scripts/demo.sh https://<votre-projet>.vercel.app

# Developpement local, sans tunnel
uv run agent-data serve                    # API sur :8000
cd web && npm install && npm run dev       # front sur :3000
```

Le lien affiche porte l'adresse du tunnel et le jeton dans son fragment (`#api=...&token=...`),
qui n'est jamais envoye a un serveur. L'URL d'un tunnel gratuit change a chaque lancement :
le front la memorise et se reconfigure via le bouton « Connexion ».

Deploiement du front : importer le depot dans Vercel avec **Root Directory = `web`**. Aucune
variable d'environnement n'est requise.

### Un modele par tache

Chaque role de l'agent peut etre servi par son propre modele (`PLANNER_MODEL`, `CODER_MODEL`,
`CRITIC_MODEL`, `SYNTHESIS_MODEL` dans `.env`, `LLM_MODEL` par defaut). Ollama charge et
decharge les modeles a chaud : sur une carte de 12 Go, un seul gros modele tient a la fois, on
paie donc un rechargement a chaque changement de role. Mesurer avant de choisir :

Choix retenu, mesure sur les trois cas d'evaluation (memes entrees pour tous les modeles) :

| Role | Modele | Ce qui a decide |
|---|---|---|
| Plan | `gemma4:e4b` | Plans les plus rigoureux (cite `Order Date`, hypotheses explicites) |
| Code | `qwen2.5-coder:14b` | Specialiste du code ; a confirmer par `run_eval.py` |
| Critique | `qwen2.5-coder:14b` | Verdicts justes en 3,6 s ; deja en VRAM apres le code, donc sans rechargement |
| Reponse | `gemma4:e4b` | Seul francais fidele aux chiffres ; qwen-coder ecrit « 42,7 % des departements » et invente une marge 2012 par categorie, llama3.2 aussi |

`llama3.2` (3B) rate un plan et un JSON de critique ; `qwen2.5:1.5b` refuse un bon resultat. Les
controles automatiques sont trop grossiers pour les departager (12/12 presque partout) : la
lecture des textes reste necessaire. Cout du changement de modele : ~11 s (qwen) a ~32 s
(gemma) de chargement a froid.

```bash
uv run python scripts/bench_models.py MODELE_A MODELE_B    # plan, critique, reponse
uv run python scripts/run_eval.py                          # code : change CODER_MODEL puis relance
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
  ui/app.py        interface Streamlit (developpement)
  api/             API FastAPI : streaming des runs vers le front web
  graph.py         boucle agentique de l'etage 1
  pipeline.py      enchainement des deux etages
  schemas.py       modeles Pydantic (contrats entre etages)
  config.py        configuration lue depuis .env
web/               front Next.js (deploye sur Vercel)
docker/            image du sandbox et helpers injectes dedans
data/              jeux de donnees locaux (non versionnes)
scripts/           setup.sh, download_data.py, run_eval.py, bench_models.py, demo.sh
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

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — schéma, patterns, passage à une data platform
- [`docs/adr/`](docs/adr/) — les décisions d'architecture et leurs raisons
- [`docs/git-workflow.md`](docs/git-workflow.md) — branches, PR, livraison
- [`docs/ci-cd.md`](docs/ci-cd.md) — pipeline, déploiement, notifications
- [`CONTRIBUTING.md`](CONTRIBUTING.md), [`SECURITY.md`](SECURITY.md), [`CHANGELOG.md`](CHANGELOG.md)

## Conventions

- **uv** partout, jamais de `pip install` direct. `pyproject.toml` et `uv.lock` versionnes.
- Branches : `main` (protegee) et `develop`. Toute feature -> `feature/...` -> PR vers `develop`, avec revue de code.
- CI sur chaque push : qualite, tests et couverture, securite, Docker, front (`make ci` en local).
- **Aucun CSV brut versionne.** Aucune cle API dans le depot.
