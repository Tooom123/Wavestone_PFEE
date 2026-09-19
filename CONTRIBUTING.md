# Contribuer

## Installation

```bash
git clone <repo> && cd Wavestone_PFEE
./scripts/setup.sh
uv run agent-data check    # verifie que tout est en place
```

## Workflow git

- `main` est protegee. `dev` porte l'integration.
- Toute contribution : branche depuis `dev` -> PR vers `dev`.
- Messages de commit courts et descriptifs, une unite de travail par commit.
- Chaque PR est relue ; la CI (`uv sync` -> `ruff` -> `pytest`) doit etre verte.

```bash
git switch dev && git pull
git switch -c feature/mon-sujet
# ... travail ...
uv run ruff check . && uv run ruff format . && uv run pytest
git push -u origin feature/mon-sujet
```

## Regles du projet

Elles viennent du cadrage avec Wavestone et ne se contournent pas sans en discuter.

1. **Le LLM ne voit jamais les donnees brutes.** Seul le `DatasetProfile` entre dans son
   contexte. Toute nouvelle information envoyee au modele doit passer par le profil.
2. **Le code genere ne s'execute que dans le sandbox.** Il n'existe aucun repli sur
   l'hote, et il ne faut pas en ajouter : sans Docker, on refuse d'executer.
3. **Aucun CSV, aucun `.env`, aucun secret dans le depot.**
4. **Pas de front web** (Next.js, React, FastAPI). L'interface est Streamlit.
5. **uv uniquement**, jamais de `pip install` direct.

## Decisions encore ouvertes

A ne pas trancher seul : choix definitif du LLM, niveau d'autonomie (validation humaine
ou bout-en-bout), budget et plafonds. En cas de besoin, prendre l'option reversible,
la mettre derriere un parametre de `config.py` et le signaler dans la PR.

## Organisation du code

| Dossier | Role |
|---|---|
| `src/agent_data/profiling/` | CSV -> `DatasetProfile` |
| `src/agent_data/planner/` | question + profil -> `AnalysisPlan` |
| `src/agent_data/executor/` | plan -> code Python |
| `src/agent_data/sandbox/` | execution isolee (Docker) |
| `src/agent_data/critic/` | relecture, correction, relance |
| `src/agent_data/rendering/` | etage 2 : artefacts -> synthese et rapport |
| `src/agent_data/eval/` | controles par etage |
| `docker/` | image du sandbox + helpers injectes dedans |

Les deux etages communiquent **uniquement** par le contrat d'artefacts (`schemas.py`).
Modifier ce contrat impacte les deux cotes : le faire en connaissance de cause.

## Tests

```bash
uv run pytest                      # tout
uv run pytest tests/test_sandbox.py -v   # isolation du sandbox (exige Docker)
uv run python scripts/run_eval.py  # evaluation sur les cas metier (long)
```

Les tests du sandbox sont ignores sans Docker. Ce sont eux qui verifient que le reseau
est coupe et qu'une boucle infinie est tuee : les lancer avant toute modification du
sandbox.

## Ajouter un jeu de donnees

Completer `DATASETS` dans `scripts/download_data.py`, puis documenter le jeu dans
`data/README.md`. Aucun CSV ne doit etre commite.

## Limites connues

- Le modele local (14B) se trompe regulierement du premier coup : appel manquant a
  `from agent_out import ...`, `df.corr()` sur des colonnes texte, encodage oublie avant
  un modele de ML. La boucle de correction rattrape ces cas ; le prompt de
  `executor/executor.py` les anticipe un par un. Ajouter une regle plutot que de
  contourner le probleme dans le code.
- Les runs qui impliquent du ML (telco_churn) sont nettement plus longs que les analyses
  descriptives : compter plusieurs minutes.
