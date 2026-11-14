# Contrôle de faisabilité du planificateur

> Généré par `scripts/run_golden.py --faisabilite` le 2026-11-14 — planificateur : gemma4:e4b. Ne pas modifier à la main.

- Questions hors périmètre refusées : **4/4**
- Questions réalisables refusées à tort : **0/20**

| Question | Attendu | Décision | Raison donnée |
|---|---|---|---|
| `agr_churn` | réalisable | ✅ réalisable | — |
| `agr_ca_profit` | réalisable | ✅ réalisable | — |
| `agr_revenu` | réalisable | ✅ réalisable | — |
| `agr_facture` | réalisable | ✅ réalisable | — |
| `cmp_contrat` | réalisable | ✅ réalisable | — |
| `cmp_seniors` | réalisable | ✅ réalisable | — |
| `cmp_enfants` | réalisable | ✅ réalisable | — |
| `cmp_segment` | réalisable | ✅ réalisable | — |
| `tmp_ca_annuel` | réalisable | ✅ réalisable | — |
| `tmp_profit` | réalisable | ✅ réalisable | — |
| `tmp_recrutement` | réalisable | ✅ réalisable | — |
| `tmp_commandes` | réalisable | ✅ réalisable | — |
| `rel_anciennete` | réalisable | ✅ réalisable | — |
| `rel_revenu_vin` | réalisable | ✅ réalisable | — |
| `rel_remise_profit` | réalisable | ✅ réalisable | — |
| `rel_facture` | réalisable | ✅ réalisable | — |
| `cls_sous_categories` | réalisable | ✅ réalisable | — |
| `cls_region` | réalisable | ✅ réalisable | — |
| `cls_depense` | réalisable | ✅ réalisable | — |
| `cls_paiement` | réalisable | ✅ réalisable | — |
| `hors_appels` | refus | ✅ refus | Le profil des données ne contient aucune colonne mesurant le nombre total d'appels passés par un client au service client. La colonne 'TechSupport' indique seulement si le service a été utilisé ('Yes'/'No'), mais pas la fréquence. |
| `hors_satisfaction` | refus | ✅ refus | Le profil des données ne contient aucune colonne représentant une 'note de satisfaction' (score, rating, etc.). Il est impossible de calculer une moyenne de satisfaction. |
| `hors_paris` | refus | ✅ refus | Le profil des données ne contient aucune colonne relative à la localisation géographique (ville, code postal) des clients, ce qui est indispensable pour répondre à la question. |
| `hors_2015` | refus | ✅ refus | La période couverte par les dates de commande (Order Date) et de livraison (Ship Date) ne dépasse pas le 30 décembre 2012. Il n'y a aucune donnée disponible pour l'année 2015. |
