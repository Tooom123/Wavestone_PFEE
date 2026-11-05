# FinOps : coûts et maintenabilité de l'agent

Point de la réunion du 23/10 : *comparer l'approche on-premise actuelle à un cloud classique,
structuré selon le cadre de [finops.org](https://www.finops.org/framework/)*.

Ce dossier répond en trois fichiers :

| Fichier | Rôle |
|---|---|
| [`benchmark.md`](benchmark.md) | Les chiffres : coût par run, points morts, sensibilité. **Généré**, ne pas modifier à la main. |
| [`mesures.json`](mesures.json) | Les mesures réelles (tokens, durée, énergie GPU) dont le benchmark part. |
| ce fichier | La méthode, le rattachement au cadre FinOps, la maintenabilité, les limites. |

Le modèle est dans [`src/agent_data/finops.py`](../../src/agent_data/finops.py) (testé) et le
générateur dans [`scripts/finops_report.py`](../../scripts/finops_report.py).

## Refaire le calcul

```bash
# 1. Mesurer (GPU, Ollama et Docker lancés) : quelques minutes par cas
uv run python scripts/run_eval.py --json docs/finops/mesures.json

# 2. Regénérer le rapport avec les hypothèses par défaut
uv run python scripts/finops_report.py

# 3. Ou avec une hypothèse de Wavestone
uv run python scripts/finops_report.py --set electricity_eur_per_kwh=0.25 --set ops_eur_per_hour=90
```

## Comment lire le benchmark

Trois modes de déploiement sont comparés sur le même run mesuré :

1. **Poste local** : la RTX 4070 SUPER de la démo (amortissement + électricité + exploitation).
2. **GPU loué** : une instance L40S (heures ouvrées ou 24 h/24) ou H100, qui fait tourner les
   mêmes modèles ouverts. Le débit est *estimé* par le rapport des bandes passantes mémoire.
3. **API de LLM** : le même volume de tokens facturé au prix public de Claude Haiku, Sonnet et
   Opus 5.5.

Chaque chiffre du rapport est soit **mesuré**, soit **sourcé** (prix public daté), soit une
**hypothèse à valider**. La section 5 du benchmark liste les hypothèses une par une avec leur
statut. Une conclusion n'est jamais plus solide que l'hypothèse la plus fragile dont elle
dépend : le coût d'exploitation (heures d'ingénieur) domine à bas volume, et c'est aussi la
valeur que nous connaissons le moins.

## Ce que dit le benchmark

Sur les 3 cas mesurés (un run moyen : 83 s, 6 126 tokens en entrée, 3 737 en sortie, 2,97 Wh
côté GPU), avec les hypothèses par défaut :

1. **L'électricité ne compte pas.** À 1 000 runs par mois, elle pèse 0,93 € sur un coût mensuel
   de 288 € (0,3 %). Doubler ou diviser par deux le prix du kWh ne change aucun classement.
2. **Le coût dominant est le temps d'exploitation.** Sur le poste local, 240 € des 288 €
   mensuels sont des heures d'ingénieur (4 h à 60 €). C'est l'hypothèse la moins connue du
   modèle : elle décide du résultat.
3. **Une API est moins chère que le poste local à faible volume.** À 1 000 runs par mois :
   0,062 € le run avec Haiku 5.5, 0,103 € avec Sonnet 5.5, 0,145 € avec Opus 5.5, contre
   0,288 € en local. Le poste ne devient moins cher que Sonnet au-delà de 5 443 runs par mois
   et qu'Opus au-delà de 2 692. Face à Haiku, le seuil (189 000) dépasse la capacité du poste
   (environ 15 800 runs par mois).
4. **Si l'exploitation du poste ne demande qu'une heure par mois**, le local coûte 0,108 € le
   run à 1 000 runs et passe sous Sonnet dès 1 131 runs par mois. Le classement dépend donc de
   cette valeur, d'où l'intérêt de la mesurer chez Wavestone plutôt que de la supposer.
5. **Louer un GPU ne se justifie pas à ce volume.** Un L40S allumé 24 h/24 coûte 1 202 € par
   mois, soit 1,20 € le run à 1 000 runs, parce que le GPU reste inactif la plupart du temps.
   Il ne vaudrait le coup qu'avec un volume qui sature un poste (plus de 15 800 runs par mois),
   ou pour des modèles qui ne tiennent pas dans 12 Go.

**Ce que le benchmark ne dit pas.** Il compare des coûts, pas des résultats. L'argument en
faveur du local n'est donc pas le prix : c'est la confidentialité (rien ne sort du poste, ce
que le cadrage Wavestone exige) et la reproductibilité (un modèle figé, pas un modèle retiré
par un fournisseur). Pour un usage réel sur données sensibles, le coût d'une API est à lire
comme un plancher que la contrainte de confidentialité peut rendre inaccessible.

## Rattachement au cadre FinOps

Le cadre organise la pratique en quatre domaines, des principes et trois phases (*Inform*,
*Optimize*, *Operate*). Ce qui existe déjà dans le projet, et ce qui reste :

| Domaine | Capacité | Dans l'agent | À faire |
|---|---|---|---|
| **Comprendre l'usage et les coûts** | Allocation | Tokens et énergie **par agent** et par run (`metrics` du flux d'événements, panneau « Ce que ce run a consommé ») | Imputer par équipe ou par client si plusieurs utilisent l'agent |
| | Reporting | Panneau du front, `benchmark.md` | Export mensuel |
| **Quantifier la valeur** | Économie unitaire | **Coût par run** (ce benchmark) | Rapprocher du temps d'analyste économisé |
| | KPI et étalonnage | Comparaison des GPU (bloc « Le matériel ») | Suivre le coût par run dans le temps |
| **Optimiser** | Architecture et placement des charges | **Ce benchmark** : local, GPU loué ou API | Décider selon le volume réel de Wavestone |
| | Optimisation de l'usage | Un modèle par rôle (ADR 0005) : le petit modèle fait le plan et la synthèse | Mesurer le gain d'un modèle plus petit par rôle |
| | Optimisation des tarifs | — | Instances spot, engagement 1 an, remise batch (−50 % chez Anthropic) |
| | Durabilité | Énergie par run en Wh | Convertir en CO₂e avec le facteur d'émission du réseau |
| **Gérer la pratique** | Prévision et budget | Modèle paramétrable | Plafond mensuel de runs ou de tokens dans l'API |
| | Gouvernance, politique et risque | Profil seul visible par le LLM, sandbox (ADR 0002, 0003) | Suivi des versions de modèles (voir plus bas) |

Phase actuelle : **Inform** (on mesure et on rend visible) ; ce benchmark prépare **Optimize**
(choisir un placement). **Operate** n'a de sens qu'avec un usage réel.

## Maintenabilité

Le coût n'est qu'un côté ; l'autre est ce qu'il faut entretenir. Évaluation qualitative, à
confronter à l'équipe d'exploitation de Wavestone.

| Critère | Poste local | GPU loué | API de LLM |
|---|---|---|---|
| **Confidentialité** | Maximale : rien ne sort | Données hébergées chez le fournisseur ; le LLM ne voit que le profil | Le profil et les traces d'erreurs expurgées partent chez un tiers |
| **Reproductibilité** | Modèle figé tant qu'on ne le met pas à jour | Idem | Le fournisseur retire des versions à son rythme ; les résultats peuvent changer |
| **Mise à jour d'un modèle** | À faire soi-même : `ollama pull`, évaluation, bascule | Idem, plus l'instance | Changer l'identifiant du modèle, mais subir les retraits |
| **Mises à jour du socle** | Pilotes NVIDIA, Ollama, Docker, système | Image et pilotes de l'instance | Aucune |
| **Disponibilité** | Un seul poste : point de défaillance unique | Redémarrage ou bascule d'instance | Gérée par le fournisseur, sous SLA |
| **Passage à l'échelle** | Limité à un run à la fois | Ajouter une instance | Illimité (limites de débit) |
| **Compétences** | GPU, Linux, Docker | Idem, plus le cloud | Intégration d'API |
| **Dépendance fournisseur** | Faible : modèles ouverts | Faible à moyenne | Forte : prix, versions, conditions |

### Suivre les versions de modèles

Le point (e) de la réunion demande de prévoir le coût de mise à jour des modèles. La mécanique
proposée, à mettre en place ensuite :

1. **Figer** : enregistrer le condensat (`digest`) de chaque modèle utilisé, pas seulement son nom.
2. **Détecter** : une commande qui compare le condensat installé au condensat figé.
3. **Autoriser une mise à jour par l'évaluation** : un nouveau modèle ne remplace l'ancien que
   si le jeu de questions de référence (golden dataset) ne régresse pas.
4. **Budgéter** : chaque mise à jour coûte une évaluation complète (durée et énergie
   mesurées par `scripts/run_eval.py`) plus du temps d'ingénieur, déjà compté dans
   `ops_hours_*`.

## Limites

- Les mesures portent sur **3 cas** de référence et un seul poste : elles donnent un ordre de
  grandeur, pas une distribution. Le golden dataset (point suivant) les fiabilisera.
- Le débit des GPU loués est **estimé** (la bande passante mémoire, pas un test sur l'instance).
  Avant toute décision, mesurer sur l'instance visée.
- Les prix d'achat actuels des GPU n'ont pas été vérifiés ; le coût du poste est une hypothèse.
- Ne sont pas comptés : stockage, trafic sortant, licences, support, coût de la panne, temps de
  développement initial. Ils pèsent peu dans un POC et beaucoup dans une plateforme.
- Une API de LLM n'offre pas la même qualité de réponse que les modèles locaux testés. Ce
  benchmark compare des **coûts**, pas des **résultats** ; la qualité relève de l'évaluation.
