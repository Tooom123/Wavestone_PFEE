# Évaluation sur le golden dataset

> Généré par `scripts/run_golden.py` le 2026-11-11 — modèles : planner = gemma4:e4b, coder = qwen2.5-coder:14b, critic = qwen2.5-coder:14b, synthesis = gemma4:e4b ; juge RAGAS : qwen2.5-coder:14b. Ne pas modifier à la main.

**17 questions réussies sur 24** en 21 min. Une question est réussie quand la réponse finale contient tous les faits attendus (ou, hors périmètre, reconnaît qu'elle ne peut pas répondre sans avancer de chiffre).

## Par catégorie

| Catégorie | Réussies | Exactitude | Rappel du contexte | Fidélité (chiffres) | RAGAS fidélité | RAGAS concordance |
|---|---|---|---|---|---|---|
| Statistique simple sur tout le jeu | 4/4 | 100 % | 100 % | 100 % | 69 % | 81 % |
| Comparaison entre groupes | 2/4 | 50 % | 50 % | 100 % | 67 % | 56 % |
| Évolution dans le temps | 4/4 | 100 % | 100 % | 88 % | 88 % | 94 % |
| Lien entre deux variables | 3/4 | 75 % | 75 % | 89 % | 88 % | 50 % |
| Classement, meilleur ou pire | 4/4 | 100 % | 100 % | 88 % | 67 % | 88 % |
| Question sans réponse dans les données | 0/4 | 0 % | — | 67 % | 72 % | 50 % |
| **Total** | 17/24 | 71 % | 85 % | 89 % | 75 % | 70 % |

## Par question

| Question |  | Exactitude | Rappel du contexte | Fidélité (chiffres) | RAGAS fidélité | RAGAS concordance | Durée | Faits manquants |
|---|---|---|---|---|---|---|---|---|
| `agr_churn` | ✅ | 100 % | 100 % | 100 % | 100 % | 75 % | 47 s | — |
| `agr_ca_profit` | ✅ | 100 % | 100 % | 100 % | 50 % | 100 % | 44 s | — |
| `agr_revenu` | ✅ | 100 % | 100 % | 100 % | 50 % | 100 % | 37 s | — |
| `agr_facture` | ✅ | 100 % | 100 % | 100 % | 75 % | 50 % | 37 s | — |
| `cmp_contrat` | ✅ | 100 % | 100 % | 100 % | 71 % | 100 % | 47 s | — |
| `cmp_seniors` | ❌ | 0 % | 0 % | 100 % | 40 % | 25 % | 57 s | taux de résiliation des seniors, taux de résiliation des autres |
| `cmp_enfants` | ❌ | 0 % | 0 % | — | 100 % | 25 % | 54 s | dépense moyenne avec enfants, dépense moyenne sans enfants |
| `cmp_segment` | ✅ | 100 % | 100 % | 100 % | 57 % | 75 % | 45 s | — |
| `tmp_ca_annuel` | ✅ | 100 % | 100 % | 50 % | 100 % | 100 % | 55 s | — |
| `tmp_profit` | ✅ | 100 % | 100 % | 100 % | 100 % | 75 % | 46 s | — |
| `tmp_recrutement` | ✅ | 100 % | 100 % | 100 % | 83 % | 100 % | 48 s | — |
| `tmp_commandes` | ✅ | 100 % | 100 % | 100 % | 67 % | 100 % | 50 s | — |
| `rel_anciennete` | ❌ | 0 % | 0 % | — | 50 % | 0 % | 64 s | ancienneté moyenne des partants (mois), ancienneté moyenne des fidèles (mois) |
| `rel_revenu_vin` | ✅ | 100 % | 100 % | 100 % | 100 % | 75 % | 106 s | — |
| `rel_remise_profit` | ✅ | 100 % | 100 % | 67 % | 100 % | 50 % | 54 s | — |
| `rel_facture` | ✅ | 100 % | 100 % | 100 % | 100 % | 75 % | 56 s | — |
| `cls_sous_categories` | ✅ | 100 % | 100 % | 100 % | 67 % | 75 % | 47 s | — |
| `cls_region` | ✅ | 100 % | 100 % | 100 % | 50 % | 100 % | 44 s | — |
| `cls_depense` | ✅ | 100 % | 100 % | 100 % | 50 % | 100 % | 50 s | — |
| `cls_paiement` | ✅ | 100 % | 100 % | 50 % | 100 % | 75 % | 48 s | — |
| `hors_appels` | ❌ | 0 % | — | 100 % | 100 % | 0 % | 51 s | reconnaître que les données ne le permettent pas |
| `hors_satisfaction` | ❌ | 0 % | — | 100 % | 62 % | 0 % | 44 s | reconnaître que les données ne le permettent pas |
| `hors_paris` | ❌ | 0 % | — | — | 50 % | 100 % | 55 s | reconnaître que les données ne le permettent pas |
| `hors_2015` | ❌ | 0 % | — | 0 % | 75 % | 100 % | 83 s | reconnaître que les données ne le permettent pas |

## Réponses

### `agr_churn` — Quel est le taux de résiliation global des clients ?

- **Attendu** : taux de résiliation : 26,5 %

> Le taux de résiliation global de votre clientèle est de 26,54 %. Ce chiffre signifie que sur l'ensemble des clients enregistrés, près d'un quart ont cessé leurs services. Plus précisément, 1 869 clients sur les 7 043 clients totaux ont résilié. Ce taux représente la proportion globale de départs observée dans l'ensemble de votre base de données.

### `agr_ca_profit` — Quel est le chiffre d'affaires total et le profit total sur l'ensemble des commandes ?

- **Attendu** : chiffre d'affaires total : 14 915 601 ; profit total : 1 521 768

> Le chiffre d'affaires total sur l'ensemble des commandes s'élève à 14 915 600,82 EUR, et le profit total atteint 1 521 767,98 EUR. Ces montants représentent la somme agrégée de toutes les transactions enregistrées. Le chiffre d'affaires total a été calculé en additionnant la colonne 'Sales', qui représente le revenu généré par chaque commande. Parallèlement, le profit total est obtenu en additionnant la colonne 'Profit', qui reflète le bénéfice net de chaque commande. Ces chiffres donnent donc une vue globale de la performance financière de l'ensemble de votre catalogue de commandes.

### `agr_revenu` — Quel est le revenu annuel moyen des clients ?

- **Attendu** : revenu annuel moyen : 52 247

> Le revenu annuel moyen de l'ensemble de votre clientèle est de 52 247,25 EUR. Ce chiffre est calculé en faisant la moyenne des données de la colonne 'Income', qui représente le revenu annuel de chaque client. Cette analyse est basée sur un échantillon de 2240 clients. En résumé, l'indicateur de revenu moyen de votre base de données est établi à 52 247,25 EUR.

### `agr_facture` — Quelle est la facture mensuelle moyenne d'un client ?

- **Attendu** : facture mensuelle moyenne : 64,8

> La facture mensuelle moyenne d'un client est de 64,76 EUR. Ce montant représente la moyenne des charges mensuelles observées sur l'ensemble de votre base de clients. Cette analyse a été réalisée en considérant toutes les données de facturation mensuelle disponibles. En résumé, si l'on prend en compte l'intégralité de votre clientèle, le coût moyen mensuel est établi à 64,76 EUR.

### `cmp_contrat` — Le taux de résiliation varie-t-il selon le type de contrat ?

- **Attendu** : taux de résiliation (Month-to-month) : 42,7 % ; taux de résiliation (One year) : 11,3 % ; taux de résiliation (Two year) : 2,8 %

> Oui, le taux de résiliation varie de manière très significative en fonction du type de contrat souscrit. Les résultats montrent une tendance très claire : les clients en contrat de type « Month-to-month » présentent le taux de résiliation le plus élevé, atteignant environ 42,7 %. Ce taux diminue fortement pour les clients en contrat d'un an (environ 11,3 %), et il est le plus bas pour ceux ayant un contrat de deux ans, avec un taux de résiliation de seulement 2,8 %. L'analyse statistique confirme que cette différence n'est pas due au hasard, ce qui indique que le type de contrat est un facteur déterminant de la fidélité de la clientèle.

### `cmp_seniors` — Les clients seniors résilient-ils davantage que les autres ?

- **Attendu** : taux de résiliation des seniors : 41,7 % ; taux de résiliation des autres : 23,6 %

> Oui, les clients seniors semblent résilier significativement moins que les autres clients. L'analyse montre une différence très marquée dans les taux de non-résiliation entre les deux groupes. En comparant les deux populations, nous observons que les seniors ont des chances de rester clients 1,24 fois plus élevées que les autres clients. De plus, le test statistique confirme que cette différence n'est pas due au hasard, avec une très forte signification (p-value de 0.0000). Ces résultats indiquent que le statut de senior est un facteur protecteur important contre le départ de la clientèle.

### `cmp_enfants` — Les clients qui ont des enfants ou des adolescents au foyer dépensent-ils moins que les autres, toutes catégories de produits confondues ?

- **Attendu** : dépense moyenne avec enfants : 406,6 ; dépense moyenne sans enfants : 1 106

> D'après l'analyse statistique, il n'y a pas de différence significative dans les habitudes de dépenses entre les clients ayant des enfants et ceux qui n'en ont pas.
> 
> En d'autres termes, la présence de dépendants ne modifie pas de manière statistiquement mesurable le niveau de dépenses moyen de la clientèle.

### `cmp_segment` — Quel segment de clientèle génère le plus de chiffre d'affaires ?

- **Attendu** : segment le plus important : Corporate ; son chiffre d'affaires : 5 498 905

> Le segment de clientèle qui génère le plus de chiffre d'affaires est sans aucun doute le segment Corporate. Ce groupe représente la source de revenus la plus importante, avec un chiffre d'affaires total de 5 498 904,88 USD. Il est nettement en avance sur les autres segments, dépassant même le segment Home Office qui est le deuxième plus performant. En comparaison, le segment Consumer génère 3 063 611,08 USD, tandis que le segment Small Business et le segment Home Office complètent le tableau avec des contributions significatives. Ces résultats montrent que la clientèle Corporate est le pilier principal de nos ventes.

### `tmp_ca_annuel` — Comment le chiffre d'affaires a-t-il évolué d'une année à l'autre de 2009 à 2012 ?

- **Attendu** : chiffre d'affaires 2009 : 4 209 139 ; chiffre d'affaires 2010 : 3 549 681 ; chiffre d'affaires 2011 : 3 436 817 ; chiffre d'affaires 2012 : 3 719 964 — ou — variation 2010 : -15,7 % ; variation 2011 : -3,2 % ; variation 2012 : 8,2 %
- **Chiffres non retrouvés dans les résultats** : 15.7, 3.2

> Le taux de croissance annuel du chiffre d'affaires entre 2009 et 2012 est de 8,24%. L'évolution annuelle montre d'abord un ralentissement significatif. En 2010, le chiffre d'affaires a chuté de manière notable, enregistrant une baisse d'environ 15,7% par rapport à 2009. Cette tendance à la baisse s'est poursuivie en 2011, avec une diminution de l'ordre de 3,2%. Cependant, une reprise est observée en 2012, l'entreprise ayant réussi à augmenter son chiffre d'affaires de 8,2% par rapport à l'année précédente.

### `tmp_profit` — Le profit de 2012 est-il supérieur à celui de 2011 ?

- **Attendu** : profit 2011 : 381 456 ; profit 2012 : 341 902

> Non, le profit de 2012 n'est pas supérieur à celui de 2011.
> 
> En comparant les résultats, le profit total généré en 2012 est de 341 901,78, tandis que le profit total en 2011 s'élève à 381 455,99. Bien que le montant de 2012 soit inférieur à celui de 2011, l'analyse statistique montre que cette différence n'est pas statistiquement significative. Cela signifie que, sur la base de ces données, on ne peut pas affirmer avec certitude que la baisse observée est due à un changement réel et non au hasard.

### `tmp_recrutement` — Combien de nouveaux clients ont été enregistrés chaque année ?

- **Attendu** : nouveaux clients 2012 : 494 ; nouveaux clients 2013 : 1 189 ; nouveaux clients 2014 : 557

> Le nombre de nouveaux clients enregistrés chaque année est de 494 en 2012, 1189 en 2013 et 557 en 2014. Ces chiffres représentent le décompte des clients uniques identifiés à chaque année, en utilisant la date d'acquisition. L'analyse montre une croissance significative des nouveaux clients entre 2012 et 2013. Au total, l'entreprise a enregistré 2240 clients uniques sur ces trois années.

### `tmp_commandes` — Quelle année a connu le plus grand nombre de commandes ?

- **Attendu** : année avec le plus de commandes : 2009 ; nombre de commandes cette année-là : 1 394

> L'année qui a connu le plus grand nombre de commandes est 2009.
> 
> Notre analyse a déterminé ce chiffre en comptant le nombre de commandes uniques pour chaque année. Selon cette méthode, l'année 2009 a enregistré 1394 commandes uniques. Bien que les années 2010 et 2012 aient également connu un volume élevé de commandes (1393 et 1392 respectivement), le total de 2009 reste le plus important. Il est important de noter que nous avons défini une commande comme étant identifiée par un numéro de commande unique.

### `rel_anciennete` — Les clients qui résilient ont-ils une ancienneté plus faible que ceux qui restent ?

- **Attendu** : ancienneté moyenne des partants (mois) : 18,0 ; ancienneté moyenne des fidèles (mois) : 37,6

> L'analyse n'a produit aucun resultat exploitable. La question doit etre reformulee ou les donnees completees.

### `rel_revenu_vin` — Quelle est la corrélation entre le revenu et les dépenses en vin ?

- **Attendu** : corrélation revenu / vin : 0,579

> La corrélation globale entre le revenu annuel des clients et leurs dépenses en vin est de 0,58. Ce chiffre indique une relation positive modérée : plus le revenu d'un client est élevé, plus il est probable qu'il dépense beaucoup en vin. Cette analyse a été réalisée sur un grand échantillon de 2216 clients. Il est important de noter que cette mesure suppose que la relation entre le revenu et les dépenses en vin est linéaire. En résumé, les clients ayant un revenu plus important ont tendance à être des acheteurs de vin plus fréquents et plus dépensiers.

### `rel_remise_profit` — Quelle est la corrélation entre la remise accordée et le profit d'une commande ?

- **Attendu** : corrélation remise / profit : -0,0371
- **Chiffres non retrouvés dans les résultats** : 1396.15

> Il existe une corrélation linéaire très faible entre la remise accordée et le profit d'une commande. Ce coefficient de -0.04 indique que, globalement, le pourcentage de remise n'est pas un prédicteur fort du profit. Cependant, en utilisant un modèle linéaire, on observe que le profit est estimé à 250,53 unités lorsque la remise est nulle. De plus, ce modèle suggère qu'une augmentation de la remise entraîne une diminution du profit, avec une perte estimée de 1396,15 unités pour chaque point de remise supplémentaire. En résumé, bien que la relation soit statistiquement faible, le modèle indique une tendance négative : plus la remise est élevée, plus le profit tend à baisser.

### `rel_facture` — La facture mensuelle est-elle plus élevée chez les clients qui partent ?

- **Attendu** : facture moyenne des partants : 74,4 ; facture moyenne des fidèles : 61,3

> Oui, la facture mensuelle est significativement plus élevée chez les clients qui annulent leur abonnement. Les résultats montrent que la moyenne des charges mensuelles est de 74,44 unités pour les clients qui partent, contre 61,27 unités pour ceux qui restent. Cette différence est statistiquement très significative, ce qui signifie que cette différence n'est pas due au hasard. De plus, l'analyse de régression confirme que plus la facture mensuelle est élevée, plus le risque de départ du client est grand. En résumé, les clients qui partent ont, en moyenne, des factures mensuelles nettement supérieures à celles des clients fidèles.

### `cls_sous_categories` — Quelles sont les trois sous-catégories de produits les plus rentables ?

- **Attendu** : n°1 des sous-catégories : Telephones and Communication ; n°2 des sous-catégories : Office Machines ; n°3 des sous-catégories : Binders and Binder Accessories

> Les trois sous-catégories de produits les plus rentables sont Téléphones et Communication, Machines de bureau, et Classeurs et accessoires de classeurs. Pour déterminer cette rentabilité, nous avons calculé le profit total cumulé pour chaque catégorie. En effet, la sous-catégorie « Téléphones et Communication » affiche le profit le plus élevé avec 316 951,62 EUR. Elle est suivie de près par « Machines de bureau » avec 307 712,93 EUR, et « Classeurs et accessoires de classeurs » qui se classe troisième avec 307 413,39 EUR. Ces résultats montrent clairement où se concentrent les plus fortes sources de revenus de l'entreprise.

### `cls_region` — Quelle région réalise le plus de ventes ?

- **Attendu** : région en tête : West ; ses ventes : 3 597 549

> La région qui réalise le plus de ventes est la région West. Cette région affiche un total de ventes de 3 597 549,28. L'analyse des données montre clairement que les ventes de la région West dépassent significativement celles des autres territoires. Par exemple, elle est nettement en avance sur la région Ontario, qui totalise 3 063 212,48. Ces chiffres confirment que la région West est, de loin, le moteur principal de nos ventes globales.

### `cls_depense` — Sur quelle catégorie de produits les clients dépensent-ils le plus au total ?

- **Attendu** : catégorie la plus dépensée : MntWines ; dépense totale dans cette catégorie : 680 816

> La catégorie de produits qui génère le revenu total le plus élevé est celle des vins (MntWines). Sur l'ensemble de la base de clients, les vins représentent un montant total dépensé de 680 816. Ce chiffre est nettement supérieur aux autres catégories. Par exemple, les produits carnés (MntMeatProducts) génèrent un revenu total de 373 968, et les produits à base de chocolat (MntSweetProducts) atteignent 60 621. Ces résultats indiquent que les vins sont, de loin, le moteur de revenus principal de l'ensemble de la clientèle.

### `cls_paiement` — Quel moyen de paiement présente le taux de résiliation le plus élevé ?

- **Attendu** : moyen de paiement le plus exposé : Electronic check ; son taux de résiliation : 45,3 %
- **Chiffres non retrouvés dans les résultats** : 20

> Le moyen de paiement qui présente le taux de résiliation le plus élevé est l'Electronic check. Ce mode de paiement affiche un taux de résiliation maximal de 45,29%. Ce chiffre est nettement supérieur aux autres moyens de paiement étudiés. Par comparaison, les taux de résiliation pour les cartes de crédit, les virements bancaires automatiques et les chèques postaux sont tous inférieurs à 20%. Ces résultats indiquent que les clients utilisant l'Electronic check sont beaucoup plus susceptibles de résilier leur service.

### `hors_appels` — Combien d'appels au service client un client passe-t-il en moyenne avant de résilier ?

- **Attendu** : Les données ne permettent pas de répondre ; la réponse doit le dire.

> En moyenne, un client qui résilie utilise environ 0,9 service de support client avant de partir. Il est important de noter que nous n'avons pas mesuré directement le nombre d'appels, mais nous avons utilisé la présence de différents services de support technique et de sécurité comme indicateur de l'engagement client. Ce chiffre de 0,9 représente la moyenne des services de support utilisés par l'ensemble des clients ayant résilié. En résumé, cela suggère que les clients qui quittent l'entreprise n'ont pas nécessairement un historique d'interactions très élevé avec nos services de support.

### `hors_satisfaction` — Quelle est la note de satisfaction moyenne des clients par région ?

- **Attendu** : Les données ne permettent pas de répondre ; la réponse doit le dire.

> Nous ne disposons pas d'une note de satisfaction directe, nous utilisons donc le profit moyen par transaction comme indicateur de satisfaction client. En effet, un profit moyen plus élevé est interprété comme un niveau de satisfaction client supérieur pour chaque région. Selon cette analyse, la région Northwest Territories présente le niveau de satisfaction le plus élevé, avec un profit moyen de 255,46. Inversement, la région Nunavut affiche le niveau de satisfaction le plus faible, avec un profit moyen de 35,96. Ces résultats montrent une variation significative de la performance client entre les régions, allant de l'Ontario (189,96) à la région West (149,18).

### `hors_paris` — Combien de clients habitent à Paris ?

- **Attendu** : Les données ne permettent pas de répondre ; la réponse doit le dire.

> Actuellement, aucun client ne réside à Paris. Cette conclusion est basée sur l'analyse des données disponibles, qui indique un total de zéro client correspondant à cette localisation. Il est important de noter que pour effectuer ce calcul, nous avons dû faire l'hypothèse qu'une colonne de localisation (Ville) existait dans le jeu de données. Par conséquent, si les informations de résidence sont stockées dans une colonne différente ou si le nom de la colonne est différent, ce résultat pourrait ne pas être représentatif. Nous vous recommandons de vérifier la structure exacte de la base de données pour confirmer la colonne contenant les informations de résidence.

### `hors_2015` — Quel chiffre d'affaires a été réalisé en 2015 ?

- **Attendu** : Les données ne permettent pas de répondre ; la réponse doit le dire.
- **Chiffres non retrouvés dans les résultats** : 31

> Le chiffre d'affaires total réalisé en 2015 est de 0.00 USD. Ce montant a été calculé en se basant sur les ventes enregistrées pour la période allant du 1er janvier au 31 décembre 2015. Il est important de noter que cette analyse repose sur le fait qu'aucune transaction n'a été trouvée pour l'année 2015. Par conséquent, le total des ventes pour cette période est nul.

