# Garde-fous et leur suivi

Point (g) de la réunion du 23/10 : *monitorer les garde-fous, le nombre de blocages par agent et
le flux qui y mène.* Le golden dataset (`docs/eval/`) a montré pourquoi c'est prioritaire :
l'agent ne disait jamais qu'une question dépassait les données (0/4), et concluait parfois à
l'inverse de ses propres chiffres.

## Les garde-fous

| Agent | Garde-fou | Ce qu'il fait |
|---|---|---|
| Planificateur | `hors_perimetre` | Avant tout calcul, le planificateur vérifie que les données couvrent la question (une colonne, une période). Sinon : arrêt, réponse fixe qui dit ce qui manque, sans LLM ni chiffre. |
| Planificateur | `colonnes_inventees` | Les colonnes absentes du profil sont retirées du plan avant de générer du code. |
| Générateur de code | `code_en_erreur` | Le code qui échoue repart vers le générateur avec l'erreur, expurgée des valeurs de données. |
| Sandbox | `delai_depasse` | Le code est tué au-delà de `SANDBOX_TIMEOUT_SECONDS`. |
| Critique | `resultat_rejete`, `replanification` | Le résultat est rejeté s'il ne répond pas au plan ; la critique peut demander un nouveau plan. |
| Boucle | `plafond_iterations` | Au bout de `MAX_ITERATIONS` essais, le meilleur résultat obtenu est rendu. |
| Humain | `plan_refuse` | Le plan peut être refusé avant toute exécution. |

S'y ajoutent deux consignes de cohérence, issues des erreurs observées :
- le planificateur prévoit, pour toute comparaison de groupes, une étape qui calcule l'indicateur
  de chaque groupe (taux, moyenne), pas seulement un test ou un coefficient ;
- la synthèse cite la valeur de chaque groupe avant de conclure, et sa conclusion va dans le
  sens de ces valeurs.

**Pourquoi la faisabilité est jugée par le planificateur.** Une règle fixe ne suffit pas :
« combien de clients à Paris ? » cite des mots qui ne sont pas des colonnes, mais « quel est le
revenu moyen ? » aussi. Le planificateur voit le profil, et désormais la **période couverte** par
chaque colonne de dates (`date_range` du profil), ce qui lui permet de refuser une question sur
2015 quand les commandes s'arrêtent en 2012. Quand il refuse, le texte de la réponse est écrit
par le code et non par le modèle : il ne peut pas proposer d'indicateur de substitution.

**Mesure** (`scripts/run_golden.py --faisabilite`, résultat dans
[`eval/faisabilite.md`](eval/faisabilite.md)) : 24 décisions justes sur 24. Les 4 questions hors
périmètre sont refusées avec la bonne raison, aucune des 20 questions réalisables ne l'est. Les 4
réponses d'abstention passent le golden dataset (elles étaient toutes en échec).

## Le suivi

Chaque déclenchement est noté dans l'ordre (`RunTrace.block`) et sort par trois voies :

1. **En direct**, un événement `guardrail` dans le flux du run (le front le reçoit).
2. **À la fin du run**, dans `metrics.guardrails` (la liste ordonnée) et
   `metrics.guardrail_counts` (par agent). Le rapport du front affiche « Garde-fous déclenchés ».
3. **Dans le temps**, une ligne par run dans un journal JSONL (`GUARDRAIL_LOG`, par défaut
   `.agent_data/garde-fous.jsonl`, non versionné). Le journal ne contient ni question ni donnée :
   jeux de données, issue du run, durée, garde-fous.

```bash
uv run agent-data garde-fous
```

```
12 run(s)

Issues :
     8  réponse produite
     3  question hors périmètre, aucun calcul
     1  plafond d'itérations atteint

Declenchements par agent :
     6  coder
     4  critic
     3  planner
     1  boucle

Enchainements les plus frequents (runs sans reponse acceptee) :
     3  planner:hors_perimetre
     1  coder:code_en_erreur x3 > critic:resultat_rejete > boucle:plafond_iterations
```

*(Sortie d'exemple : la forme, pas une mesure.)*

## Vers une data platform

Le journal est volontairement un fichier plat : en production, la même ligne part vers l'outil de
supervision de la plateforme (Langfuse est déjà configurable dans `config.py`, ou une table de
logs). Les indicateurs à suivre : part des runs hors périmètre (questions que les utilisateurs
posent et que les données ne couvrent pas, utile pour savoir quelles données ajouter), part des
runs au plafond, et l'agent qui bloque le plus.
