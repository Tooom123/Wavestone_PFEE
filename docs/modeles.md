# Versions des modèles : figer, détecter, mettre à jour

Point (e) de la réunion du 23/10 : *prendre en compte les coûts de maintenance, notamment le
suivi des montées de version des modèles.*

## Le problème

Un nom Ollama n'est pas une version. `qwen2.5-coder:14b` désigne ce que le registre sert au
moment du `ollama pull` : si une révision est publiée sous le même nom, un nouveau poste (ou un
`pull` de routine) installe un autre modèle, et les réponses de l'agent changent sans que rien
ne le signale. Pour un livrable évalué sur un golden dataset, c'est une régression silencieuse
possible.

## Le verrou

[`models.lock.json`](../models.lock.json), versionné, enregistre pour chaque agent le modèle, son
**condensat** (`digest`, qui change à chaque révision), sa taille et sa quantification, la
version d'Ollama, et **le score du golden dataset obtenu avec ces modèles** : 17/24 au
11/11/2026, par catégorie.

| Commande | Rôle |
|---|---|
| `uv run agent-data modeles verifier` | Le poste sert-il exactement les modèles figés ? Code de sortie 1 sinon. |
| `uv run agent-data check` | Inclut la même vérification, avec Docker et les données. |
| `uv run agent-data modeles figer --golden docs/eval/resultats.json` | Fige les modèles actuels avec le score d'une évaluation. Refuse si l'évaluation a été faite avec d'autres modèles, ou si le score régresse (`--force` pour passer outre). |
| `uv run python scripts/upgrade_model.py --role coder --model <candidat> --pull` | Change le modèle d'un agent **seulement si le golden dataset ne régresse pas**. |

Écarts détectés : `modele_change` (la configuration ne désigne plus le modèle figé),
`version_changee` (même nom, autre condensat : re-évaluer), `absent` (pas installé),
`non_fige` (pas de verrou). Un test de la CI vérifie que le verrou et `.env.example` désignent
les mêmes modèles.

## Mettre à jour un modèle

`scripts/upgrade_model.py` :

1. installe le candidat (`--pull`) ;
2. fait tourner le golden dataset avec ce modèle pour ce seul rôle ;
3. compare au verrou : **le total, et chaque catégorie**. Une catégorie qui baisse bloque, même si
   le total monte : un modèle meilleur en classement mais qui invente hors périmètre n'est pas un
   meilleur modèle pour un décideur ;
4. sans régression, met à jour le verrou et donne la ligne de `.env` à changer ; sinon, laisse le
   verrou intact et liste les régressions.

Le même script re-valide un modèle dont la version a changé sous le même nom (`--model` = le nom
actuel).

## Ce que coûte une mise à jour

| Poste | Valeur | Statut |
|---|---|---|
| Durée d'un passage du golden dataset | 21 min (24 questions) | mesuré le 11/11/2026 |
| Énergie GPU d'un passage | ≈ 45 Wh, soit < 0,01 € d'électricité | estimé : ~130 W moyens mesurés pendant les runs × 21 min |
| Notation RAGAS optionnelle | ≈ 10 min | mesuré |
| Relecture humaine des échecs (`docs/eval/resultats.md`) | ≈ 1 h | hypothèse |
| Téléchargement du modèle | 5 à 10 Go | mesuré (tailles Ollama) |

Le coût est donc presque entièrement du **temps d'ingénieur**, comme le montre le benchmark FinOps
(`docs/finops/`, hypothèses `ops_hours_*`). À raison d'une révision de modèle par trimestre et par
famille (Qwen, Gemma), compter de l'ordre de 2 h par trimestre. La fréquence réelle des révisions
n'est pas connue : c'est une hypothèse à suivre avec `agent-data modeles verifier`.

À comparer avec une API de LLM : pas de téléchargement ni de verrou à tenir, mais le fournisseur
retire les versions à son rythme et l'évaluation doit être refaite à chaque retrait, sans pouvoir
garder l'ancien modèle.

## Limites

- Le condensat garantit le modèle, pas le résultat : la génération de code varie d'un run à
  l'autre. Comparer deux modèles sur un seul passage reste fragile ; sur une décision serrée, faire
  deux passages.
- Le verrou ne fige pas la version d'Ollama, il la note : une montée d'Ollama peut changer
  l'inférence. `agent-data modeles verifier` la montre ; la re-évaluation reste manuelle.
