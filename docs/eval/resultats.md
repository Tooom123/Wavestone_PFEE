# Évaluation sur le golden dataset

> Généré par `scripts/run_golden.py` le 2026-11-15 — modèles : planner = gemma4:e4b, coder = qwen2.5-coder:14b, critic = qwen2.5-coder:14b, synthesis = gemma4:e4b. Ne pas modifier à la main.

**22 questions réussies sur 24** en 20 min. Une question est réussie quand la réponse finale contient tous les faits attendus (ou, hors périmètre, reconnaît qu'elle ne peut pas répondre sans avancer de chiffre).

## Par catégorie

| Catégorie | Réussies | Exactitude | Rappel du contexte | Fidélité (chiffres) |
|---|---|---|---|---|
| Statistique simple sur tout le jeu | 4/4 | 100 % | 100 % | 88 % |
| Comparaison entre groupes | 2/4 | 50 % | 75 % | 89 % |
| Évolution dans le temps | 4/4 | 100 % | 100 % | 93 % |
| Lien entre deux variables | 4/4 | 100 % | 100 % | 100 % |
| Classement, meilleur ou pire | 4/4 | 100 % | 100 % | 100 % |
| Question sans réponse dans les données | 4/4 | 100 % | — | — |
| **Total** | 22/24 | 92 % | 95 % | 94 % |

## Par question

| Question |  | Exactitude | Rappel du contexte | Fidélité (chiffres) | Durée | Faits manquants |
|---|---|---|---|---|---|---|
| `agr_churn` | ✅ | 100 % | 100 % | 100 % | 110 s | — |
| `agr_ca_profit` | ✅ | 100 % | 100 % | 100 % | 51 s | — |
| `agr_revenu` | ✅ | 100 % | 100 % | 100 % | 37 s | — |
| `agr_facture` | ✅ | 100 % | 100 % | 50 % | 41 s | — |
| `cmp_contrat` | ❌ | 0 % | 100 % | 100 % | 55 s | taux de résiliation (Month-to-month), taux de résiliation (One year), taux de résiliation (Two year) |
| `cmp_seniors` | ❌ | 0 % | 0 % | — | 94 s | taux de résiliation des seniors, taux de résiliation des autres |
| `cmp_enfants` | ✅ | 100 % | 100 % | 67 % | 72 s | — |
| `cmp_segment` | ✅ | 100 % | 100 % | 100 % | 47 s | — |
| `tmp_ca_annuel` | ✅ | 100 % | 100 % | 71 % | 103 s | — |
| `tmp_profit` | ✅ | 100 % | 100 % | 100 % | 48 s | — |
| `tmp_recrutement` | ✅ | 100 % | 100 % | 100 % | 75 s | — |
| `tmp_commandes` | ✅ | 100 % | 100 % | 100 % | 48 s | — |
| `rel_anciennete` | ✅ | 100 % | 100 % | 100 % | 57 s | — |
| `rel_revenu_vin` | ✅ | 100 % | 100 % | 100 % | 45 s | — |
| `rel_remise_profit` | ✅ | 100 % | 100 % | 100 % | 50 s | — |
| `rel_facture` | ✅ | 100 % | 100 % | 100 % | 52 s | — |
| `cls_sous_categories` | ✅ | 100 % | 100 % | 100 % | 47 s | — |
| `cls_region` | ✅ | 100 % | 100 % | 100 % | 44 s | — |
| `cls_depense` | ✅ | 100 % | 100 % | 100 % | 53 s | — |
| `cls_paiement` | ✅ | 100 % | 100 % | 100 % | 47 s | — |
| `hors_appels` | ✅ | 100 % | — | — | 8 s | — |
| `hors_satisfaction` | ✅ | 100 % | — | — | 21 s | — |
| `hors_paris` | ✅ | 100 % | — | — | 8 s | — |
| `hors_2015` | ✅ | 100 % | — | — | 8 s | — |

## Réponses

### `agr_churn` — Quel est le taux de résiliation global des clients ?

- **Attendu** : taux de résiliation : 26,5 %

> Le taux de résiliation global de votre clientèle est de 26,54 %. Cela signifie que sur l'ensemble des 7043 clients enregistrés dans l'échantillon, 1869 clients ont résilié leur service. Ce taux représente la proportion de clients ayant quitté l'entreprise par rapport au nombre total de clients. En résumé, un peu plus d'un quart de votre base de clientèle a résilié.

### `agr_ca_profit` — Quel est le chiffre d'affaires total et le profit total sur l'ensemble des commandes ?

- **Attendu** : chiffre d'affaires total : 14 915 601 ; profit total : 1 521 768

> Le chiffre d'affaires total généré par l'ensemble des commandes s'élève à 14 915 600,82 USD. Parallèlement, le profit total réalisé sur ces mêmes commandes atteint 1 521 767,98 USD. Ces montants représentent la somme complète des ventes et des bénéfices enregistrés dans le jeu de données. En résumé, l'activité globale affiche un chiffre d'affaires de près de 15 millions de dollars, avec un profit total de plus d'un million et demi de dollars.

### `agr_revenu` — Quel est le revenu annuel moyen des clients ?

- **Attendu** : revenu annuel moyen : 52 247

> Le revenu annuel moyen de l'ensemble de votre clientèle est de 52 247,25 EUR. Ce calcul repose sur l'hypothèse que la colonne 'Income' représente bien le revenu annuel de chaque client. Ce chiffre est une moyenne calculée sur un échantillon de 2240 clients. En résumé, vous pouvez considérer que le revenu annuel moyen de votre base de données est de 52 247,25 EUR.

### `agr_facture` — Quelle est la facture mensuelle moyenne d'un client ?

- **Attendu** : facture mensuelle moyenne : 64,8
- **Chiffres non retrouvés dans les résultats** : 100

> La facture mensuelle moyenne d'un client est de 64,76 EUR. Ce montant représente la moyenne arithmétique de toutes les charges mensuelles enregistrées pour l'ensemble de notre clientèle. Pour obtenir ce résultat, nous avons calculé la moyenne de la colonne MonthlyCharges sur l'intégralité du panel de clients. Ce chiffre est considéré comme très fiable, avec un niveau de confiance de 100%.

### `cmp_contrat` — Le taux de résiliation varie-t-il selon le type de contrat ?

- **Attendu** : taux de résiliation (Month-to-month) : 42,7 % ; taux de résiliation (One year) : 11,3 % ; taux de résiliation (Two year) : 2,8 %

> Oui, le taux de résiliation varie de manière significative en fonction du type de contrat souscrit. Les clients avec un contrat « Month-to-month » présentent le taux de résiliation le plus élevé, atteignant 26,54 %. Ce taux est nettement supérieur à celui des contrats « One year », qui est de 13,97 %. Enfin, les contrats « Two year » affichent le taux le plus faible, avec seulement 8,05 % de résiliation. Il est donc clair que la durée de l'engagement contractuel est un facteur déterminant dans la rétention de la clientèle.

### `cmp_seniors` — Les clients seniors résilient-ils davantage que les autres ?

- **Attendu** : taux de résiliation des seniors : 41,7 % ; taux de résiliation des autres : 23,6 %

> L'analyse n'a produit aucun resultat exploitable. La question doit etre reformulee ou les donnees completees.

### `cmp_enfants` — Les clients qui ont des enfants ou des adolescents au foyer dépensent-ils moins que les autres, toutes catégories de produits confondues ?

- **Attendu** : dépense moyenne avec enfants : 406,6 ; dépense moyenne sans enfants : 1 106
- **Chiffres non retrouvés dans les résultats** : 1512.03

> Non, les données indiquent que les clients ayant des enfants ou des adolescents dépensent significativement moins que les clients n'ayant pas de jeunes dépendants.
> 
> En effet, l'analyse des dépenses moyennes montre que :
> 
> *   Les clients avec des enfants ou des adolescents dépensent en moyenne **406,03 €**.
> *   Les clients sans enfants ou adolescents dépensent en moyenne **1 512,03 €**.
> 
> Cette différence de plus de 1 100 € de dépenses moyennes suggère une corrélation inverse entre la présence de jeunes dépendants et le niveau de dépenses global.

### `cmp_segment` — Quel segment de clientèle génère le plus de chiffre d'affaires ?

- **Attendu** : segment le plus important : Corporate ; son chiffre d'affaires : 5 498 905

> Le segment de clientèle qui génère le plus de chiffre d'affaires est Corporate, avec un total de 5 498 904 euros. En comparant les quatre segments, nous observons que Corporate est nettement en tête. Le segment Home Office suit avec 3 564 764 euros, tandis que les Consumer génèrent 3 063 611 euros. Enfin, le segment Small Business représente le plus faible chiffre d'affaires avec 2 788 321 euros. Il est donc clair que le segment Corporate est le principal moteur de revenus de l'entreprise.

### `tmp_ca_annuel` — Comment le chiffre d'affaires a-t-il évolué d'une année à l'autre de 2009 à 2012 ?

- **Attendu** : chiffre d'affaires 2009 : 4 209 139 ; chiffre d'affaires 2010 : 3 549 681 ; chiffre d'affaires 2011 : 3 436 817 ; chiffre d'affaires 2012 : 3 719 964 — ou — variation 2010 : -15,7 % ; variation 2011 : -3,2 % ; variation 2012 : 8,2 %
- **Chiffres non retrouvés dans les résultats** : 15.67, 3.18

> Le chiffre d'affaires a connu une baisse significative entre 2009 et 2011, avant de se redresser notablement en 2012. En 2009, le chiffre d'affaires total était de 4 209 139,46 $. Cette valeur a chuté de 15,67 % en 2010, atteignant 3 549 680,80 $. La baisse a continué en 2011, avec une diminution de 3,18 % par rapport à l'année précédente, portant le chiffre d'affaires à 3 436 816,70 $. Cependant, l'année 2012 marque un retour en croissance, avec une augmentation de 8,24 % pour atteindre 3 719 963,86 $. En résumé, après un pic en 2009, l'activité a connu un creux puis une reprise en 2012.

### `tmp_profit` — Le profit de 2012 est-il supérieur à celui de 2011 ?

- **Attendu** : profit 2011 : 381 456 ; profit 2012 : 341 902

> Non, le profit total de 2012 n'est pas supérieur à celui de 2011. Pour effectuer cette comparaison, nous avons calculé la somme totale des profits pour chaque année. Le profit total enregistré en 2011 s'élève à 381 455,99. Par comparaison, le profit total de 2012 est de 341 901,78. Ces valeurs montrent clairement que le profit de 2012 est inférieur au profit de 2011.

### `tmp_recrutement` — Combien de nouveaux clients ont été enregistrés chaque année ?

- **Attendu** : nouveaux clients 2012 : 494 ; nouveaux clients 2013 : 1 189 ; nouveaux clients 2014 : 557

> Le nombre de nouveaux clients enregistrés varie significativement selon les années analysées. En 2012, 494 clients uniques ont été enregistrés, ce chiffre a fortement augmenté en 2013 pour atteindre 1 189 clients. Cependant, on observe un recul en 2014, avec 557 clients uniques enregistrés. En résumé, l'analyse des données disponibles montre une croissance très marquée entre 2012 et 2013, suivie d'une diminution en 2014.

### `tmp_commandes` — Quelle année a connu le plus grand nombre de commandes ?

- **Attendu** : année avec le plus de commandes : 2009 ; nombre de commandes cette année-là : 1 394

> L'année qui a connu le plus grand nombre de commandes est 2009, avec un total de 1394 commandes uniques.
> 
> Pour déterminer ce chiffre, nous avons compté le nombre d'identifiants de commande uniques pour chaque année. En comparant les données, nous observons que 2009 a dépassé les autres années. Il a enregistré 1394 commandes, ce qui est légèrement supérieur à 2010 (1393 commandes) et 2012 (1392 commandes). L'année 2011, quant à elle, a connu le plus faible volume avec 1317 commandes.

### `rel_anciennete` — Les clients qui résilient ont-ils une ancienneté plus faible que ceux qui restent ?

- **Attendu** : ancienneté moyenne des partants (mois) : 18,0 ; ancienneté moyenne des fidèles (mois) : 37,6

> Oui, les clients qui résilient ont en moyenne une ancienneté significativement plus faible que ceux qui restent. En comparant les deux groupes, nous constatons que la moyenne d'ancienneté des clients ayant résilié est de 17.98 mois. Cette valeur est nettement inférieure à la moyenne des clients qui restent, qui est de 37.57 mois. Ces résultats indiquent clairement que les départs surviennent majoritairement après une période d'engagement plus courte.

### `rel_revenu_vin` — Quelle est la corrélation entre le revenu et les dépenses en vin ?

- **Attendu** : corrélation revenu / vin : 0,579

> Oui, il existe une corrélation positive entre le revenu annuel des clients et le montant qu'ils dépensent en vin. Cela signifie que plus le revenu d'un client est élevé, plus il a tendance à dépenser en vin. Le coefficient de corrélation calculé est de 0,58, ce qui indique une relation positive de force modérée entre ces deux variables. En termes simples, les clients ayant un revenu plus important sont plus susceptibles d'être des acheteurs de vin plus dépensiers.

### `rel_remise_profit` — Quelle est la corrélation entre la remise accordée et le profit d'une commande ?

- **Attendu** : corrélation remise / profit : -0,0371

> Il n'y a pas de lien fort entre la remise accordée et le profit généré par une commande. Le coefficient de corrélation calculé est de -0,04, ce qui indique une relation très faible. En termes simples, cela signifie que même si une remise plus élevée est associée à un profit légèrement plus faible, cette relation est négligeable. Autrement dit, le niveau de remise que vous accordez ne semble pas être un facteur déterminant de la rentabilité de la commande. Vous pouvez donc considérer que la remise accordée n'est pas le principal moteur de variation de votre profit.

### `rel_facture` — La facture mensuelle est-elle plus élevée chez les clients qui partent ?

- **Attendu** : facture moyenne des partants : 74,4 ; facture moyenne des fidèles : 61,3

> Oui, la facture mensuelle est significativement plus élevée chez les clients qui partent. En comparant les deux groupes, nous observons que la moyenne des charges mensuelles pour les clients qui ont résilié est de 74,44, contre 61,27 pour ceux qui sont restés. Cette différence de 13,18 indique que les clients qui partent paient en moyenne beaucoup plus cher que ceux qui restent. Il est donc établi que les clients qui résilient sont associés à des factures mensuelles plus importantes.

### `cls_sous_categories` — Quelles sont les trois sous-catégories de produits les plus rentables ?

- **Attendu** : n°1 des sous-catégories : Telephones and Communication ; n°2 des sous-catégories : Office Machines ; n°3 des sous-catégories : Binders and Binder Accessories

> Les trois sous-catégories de produits les plus rentables sont Téléphones et Communication, Office Machines, et Binders and Binder Accessories. Pour déterminer la rentabilité, nous avons utilisé le profit total cumulé de chaque sous-catégorie. Ces trois catégories affichent les profits les plus élevés, avec Téléphones et Communication à 316 951,62, suivi par Office Machines à 307 712,93, et Binders and Binder Accessories à 307 413,39. Ces résultats indiquent que ces trois domaines sont les principaux moteurs de profit pour l'entreprise.

### `cls_region` — Quelle région réalise le plus de ventes ?

- **Attendu** : région en tête : West ; ses ventes : 3 597 549

> La région qui réalise le plus de ventes est la région West. Avec un montant total de ventes de 3 597 549,28, elle est nettement en tête des régions analysées. Pour comparaison, la région Ontario affiche 3 063 212,48, et la région Prarie suit avec 2 837 304,60. Ces chiffres confirment que la région West est de loin le moteur de ventes le plus important.

### `cls_depense` — Sur quelle catégorie de produits les clients dépensent-ils le plus au total ?

- **Attendu** : catégorie la plus dépensée : MntWines ; dépense totale dans cette catégorie : 680 816

> Les clients dépensent le plus au total dans la catégorie Vins.
> 
> Selon l'analyse des dépenses cumulées, la catégorie Vins représente la dépense la plus élevée avec 680 816 euros. Pour déterminer ce montant, nous avons additionné les dépenses de chaque client pour chaque type de produit. En comparant les montants totaux, les Vins (680 816 euros) dépassent significativement les Produits Carnés (373 968 euros) et les Produits Or (98 609 euros). Il est donc clair que les Vins constituent la source de revenus la plus importante pour l'ensemble de la clientèle.

### `cls_paiement` — Quel moyen de paiement présente le taux de résiliation le plus élevé ?

- **Attendu** : moyen de paiement le plus exposé : Electronic check ; son taux de résiliation : 45,3 %

> Le moyen de paiement qui présente le taux de résiliation le plus élevé est le chèque électronique (Electronic check). Ce mode de paiement affiche un taux de résiliation de 45,29%, ce qui est nettement supérieur aux autres options. Pour comparaison, le chèque par courrier (Mailed check) présente un taux de résiliation de 19,11%, tandis que le virement bancaire automatique (Bank transfer) est à 16,71% et la carte de crédit automatique (Credit card) est à 15,24%. Il est donc clair que le chèque électronique est le moyen de paiement le plus associé à un risque de départ élevé pour les clients.

### `hors_appels` — Combien d'appels au service client un client passe-t-il en moyenne avant de résilier ?

- **Attendu** : Les données ne permettent pas de répondre ; la réponse doit le dire.

> Les données disponibles ne permettent pas de répondre à cette question : Le profil des données ne contient aucune colonne mesurant le nombre d'appels passés par un client au service client. Il n'existe pas de variable de fréquence d'appels. Aucun calcul n'a été lancé. Pour y répondre, il faudrait des données qui contiennent cette information.

### `hors_satisfaction` — Quelle est la note de satisfaction moyenne des clients par région ?

- **Attendu** : Les données ne permettent pas de répondre ; la réponse doit le dire.

> Les données disponibles ne permettent pas de répondre à cette question : Le profil des données ne contient aucune colonne représentant une 'note de satisfaction' (rating, score, feedback, etc.). Il est impossible de calculer une moyenne de satisfaction. Aucun calcul n'a été lancé. Pour y répondre, il faudrait des données qui contiennent cette information.

### `hors_paris` — Combien de clients habitent à Paris ?

- **Attendu** : Les données ne permettent pas de répondre ; la réponse doit le dire.

> Les données disponibles ne permettent pas de répondre à cette question : Le jeu de données ne contient aucune colonne permettant d'identifier la ville ou la localisation géographique des clients (ex: 'City', 'Region', 'Adresse'). Aucun calcul n'a été lancé. Pour y répondre, il faudrait des données qui contiennent cette information.

### `hors_2015` — Quel chiffre d'affaires a été réalisé en 2015 ?

- **Attendu** : Les données ne permettent pas de répondre ; la réponse doit le dire.

> Les données disponibles ne permettent pas de répondre à cette question : La colonne 'Order Date' ne couvre que la période du 2009-01-01 au 2012-12-30, et ne contient aucune donnée pour l'année 2015. Aucun calcul n'a été lancé. Pour y répondre, il faudrait des données qui contiennent cette information.

