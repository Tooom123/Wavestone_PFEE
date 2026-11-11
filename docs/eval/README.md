# Évaluation : golden dataset et métriques à la RAGAS

Point (c) de la réunion du 23/10 : *construire un golden dataset de 20 à 30 questions en 5 à 6
catégories, avec les bonnes réponses et les sorties attendues réelles, puis tester une
librairie de type RAGAS.*

| Fichier | Rôle |
|---|---|
| [`golden.json`](golden.json) | Les 24 questions et leurs réponses attendues, **figées**. C'est la vérité terrain. |
| `resultats.md` / `resultats.json` | Les réponses de l'agent et leurs notes (produits par `run_golden.py`). |
| [`src/agent_data/eval/golden.py`](../../src/agent_data/eval/golden.py) | Les questions et le calcul pandas de chaque réponse attendue. |
| [`src/agent_data/eval/metrics.py`](../../src/agent_data/eval/metrics.py) | Les métriques déterministes. |
| [`scripts/ragas_golden.py`](../../scripts/ragas_golden.py) | La notation par RAGAS, avec un juge local. |

## Faire tourner l'évaluation

```bash
uv run python scripts/build_golden.py --check   # golden.json correspond-il encore aux CSV ?
uv run python scripts/run_golden.py             # l'agent répond aux 24 questions (~35 min)
uv run scripts/ragas_golden.py                  # optionnel : notes RAGAS (~5 min)
uv run python scripts/run_golden.py --rapport   # régénère resultats.md avec les notes RAGAS
```

`run_golden.py` exige Ollama, le GPU, Docker et les CSV de `data/`. Il accepte `--category`,
`--case` et `--juge` (note de pertinence par le modèle local).

## Le golden dataset

24 questions, 4 par catégorie, réparties sur les trois jeux de données :

| Catégorie | Ce qu'elle teste | Exemple |
|---|---|---|
| `agregat` | Une statistique sur tout le jeu | « Quel est le taux de résiliation global des clients ? » → 26,5 % |
| `comparaison` | Un écart entre groupes | « Les clients seniors résilient-ils davantage ? » → 41,7 % contre 23,6 % |
| `temporel` | Une évolution dans le temps | « Le profit de 2012 est-il supérieur à celui de 2011 ? » → non : 341 902 contre 381 456 |
| `relation` | Le lien entre deux variables | « Quelle est la corrélation entre le revenu et les dépenses en vin ? » → 0,58 |
| `classement` | Le meilleur ou le pire | « Quel moyen de paiement a le taux de résiliation le plus élevé ? » → Electronic check, 45,3 % |
| `hors_perimetre` | Une question sans réponse dans les données | « Combien de clients habitent à Paris ? » → l'agent doit dire qu'il ne peut pas répondre |

Chaque réponse attendue est une liste de **faits** :
- un **nombre**, avec une tolérance (3 % par défaut, absolue pour les corrélations) et son unité :
  pour un pourcentage, « 26,5 % » et « 0,265 » sont acceptés tous les deux ;
- une **étiquette** (« Corporate », « West »), avec ses traductions (« entreprises », « ouest ») ;
- une **abstention**, pour les questions hors périmètre.

**Les réponses viennent des données, pas d'un LLM.** Chaque question a une fonction pandas qui
calcule ses faits. `build_golden.py` l'exécute sur les vrais CSV et écrit `golden.json`, que
l'on relit avant de le commiter. Les CSV ne sont pas versionnés (cadrage Wavestone), mais les
réponses attendues le sont : ce sont des agrégats. La CI vérifie que `golden.json` reste cohérent
avec les questions du code.

Pour ajouter une question : l'écrire dans `QUESTIONS` avec sa fonction de référence, lancer
`build_golden.py`, relire le diff de `golden.json`.

## Les métriques

RAGAS juge une réponse avec un LLM. Ici la vérité terrain est chiffrée : les mêmes propriétés se
vérifient de façon **déterministe**, reproductible et gratuite.

| Métrique | Équivalent RAGAS | Question |
|---|---|---|
| Exactitude | answer correctness | La réponse finale contient-elle les faits attendus ? |
| Rappel du contexte | context recall | Les résultats calculés à l'étage 1 contiennent-ils ces faits ? |
| Fidélité (chiffres) | faithfulness | Les chiffres de la réponse viennent-ils des résultats, ou sont-ils inventés ? |
| Pertinence (juge, optionnel) | answer relevancy | La réponse traite-t-elle la question ? Note 1 à 5 par le modèle local. |

**Une question est réussie** quand la réponse contient tous les faits attendus. Hors périmètre,
quand elle reconnaît ne pas pouvoir répondre *sans avancer de chiffre* : « les données ne
contiennent pas la ville, mais environ 312 clients seraient parisiens » échoue.

**Situer l'erreur.** Rappel du contexte haut et exactitude basse : l'étage 1 avait le bon chiffre,
la synthèse l'a perdu. Rappel bas : l'étage 1 a mal calculé ou n'a pas calculé.

## Test de RAGAS

Nous avons testé [RAGAS](https://github.com/explodinggradients/ragas) 0.4.3, avec un juge local
(Ollama, par son API compatible OpenAI) pour que rien ne sorte du poste. Trois métriques ont été
essayées sur quatre réponses dont on connaît le bon verdict.

| Réponse | Verdict attendu | Nos métriques | RAGAS fidélité | RAGAS exactitude factuelle | RAGAS concordance |
|---|---|---|---|---|---|
| Juste (26,5 %) | réussite | réussite | 1 | 1 | 1 |
| Chiffre faux (31,2 %) | échec | échec | 0 | 0 | 0,25 |
| Invente une affirmation sans chiffre (« les Parisiens résilient deux fois plus ») | échec | **réussite, à tort** | 0,5 | 0,67 | 0,75 |
| Abstention correcte (« aucune donnée de localisation ») | réussite | réussite | **0, à tort** | **0, à tort** | 1 |

Juge `qwen2.5-coder:14b` : notes identiques sur deux passages, 20 à 25 s par réponse pour les trois
métriques. Juge `gemma4:e4b` : deux à cinq fois plus lent, sorties tronquées (erreur
`IncompleteOutputException`), notes incohérentes.

**Ce que nous en retenons.**

1. **Les deux approches se complètent.** Nos métriques ne vérifient que les chiffres : une
   affirmation inventée sans chiffre leur échappe. La fidélité RAGAS la repère, parce qu'elle
   découpe la réponse en affirmations et vérifie chacune contre les résultats.
2. **RAGAS se trompe sur les abstentions.** Une réponse qui dit honnêtement « les données ne le
   permettent pas » est notée 0 en fidélité et en exactitude factuelle. Nos métriques jugent
   donc la catégorie hors périmètre ; RAGAS n'y sert pas.
3. **Nous gardons la fidélité et la concordance RAGAS, en complément.** L'exactitude factuelle
   (`FactualCorrectness`) n'apporte rien que nos faits chiffrés ne mesurent mieux.
4. **La réussite d'une question reste définie par nos métriques**, reproductibles et
   indépendantes d'un juge. Les notes RAGAS s'affichent à côté pour signaler une réponse à relire.

**Pièges rencontrés, utiles à qui reprendra le projet :**
- RAGAS 0.4.3 ne s'importe pas avec `langchain-community` 0.4 (module `vertexai` retiré) :
  il faut `langchain-community<0.4`.
- Il exige un client **asynchrone** (`AsyncOpenAI`). Avec un client synchrone, `Faithfulness`
  lève une erreur, mais `AnswerAccuracy` renvoie `NaN` sans rien signaler.
- Ajouté comme dépendance optionnelle du projet, il fait bouger les versions de LangGraph et
  LangChain utilisées par l'agent (et redescend `rich` de la 15 à la 14). D'où le script
  autonome : `uv run scripts/ragas_golden.py` l'installe dans un environnement à part (en-tête
  PEP 723 du script), sans toucher aux dépendances de l'agent.

## Limites

- **Une réponse juste peut échouer** si elle exprime le fait autrement que prévu : un écart en
  points au lieu des deux taux, un arrondi au-delà de la tolérance, une traduction non listée.
  Lire les faits manquants dans `resultats.md` avant de conclure à une erreur de l'agent.
- **Une seule exécution ne suffit pas** : la génération de code varie d'un run à l'autre. Juger
  sur plusieurs passages avant de comparer deux versions de modèles.
- **La modélisation n'est pas couverte** : une classification ou un clustering n'ont pas de
  réponse unique à figer. Les trois cas historiques (`scripts/run_eval.py`) restent l'épreuve
  de ces familles.
- Les questions portent sur des jeux de quelques milliers de lignes. Le passage à plusieurs Go
  est le point (d) de la réunion.
