# Benchmark coûts : on-premise contre cloud

> Généré le 2026-11-05 par `scripts/finops_report.py` à partir de `mesures.json`. Ne pas modifier à la main : changer une hypothèse et regénérer.

## 1. Ce que coûte un run (mesuré)

| Grandeur | Valeur |
|---|---|
| Durée moyenne | 83 s |
| Tokens en entrée | 6 126 |
| Tokens en sortie | 3 737 |
| Énergie GPU | 2,97 Wh |

Mesures faites sur la RTX 4070 SUPER avec `qwen2.5-coder:14b` et `gemma4:e4b`, sur les cas de référence de `agent_data.eval`. L'énergie est celle du GPU seul (`nvidia-smi`) ; le reste du poste est une hypothèse.

## 2. Coût par run selon le volume mensuel

| Mode | 100 runs/mois | 1 000 runs/mois | 10 000 runs/mois |
|---|---|---|---|
| Poste local (RTX 4070 SUPER) | 2,87 € | 0,288 € | 0,030 € |
| GPU loué L40S, heures ouvrées | 4,26 € | 0,426 € | 0,043 € ⚠ saturé |
| GPU loué L40S, 24 h/24 | 12,02 € | 1,20 € | 0,120 € |
| GPU loué H100, 24 h/24 | 21,73 € | 2,17 € | 0,217 € |
| API Claude Haiku 5.5 | 0,602 € | 0,062 € | 0,0081 € |
| API Claude Sonnet 5.5 | 0,643 € | 0,103 € | 0,049 € |
| API Claude Opus 5.5 | 0,685 € | 0,145 € | 0,091 € |

« ⚠ saturé » : le volume dépasse ce que la machine peut absorber (50 % d'occupation, un run à la fois) ; le coût affiché est alors théorique. Une API n'a pas de limite de capacité.

### Détail mensuel à 1 000 runs

| Mode | Total / mois | Fixe | Variable | Capacité (runs/mois) |
|---|---|---|---|---|
| Poste local (RTX 4070 SUPER) | 288,15 € | amortissement 47,22 €, exploitation 240,00 € | électricité 0,932 € | 15 838 |
| GPU loué L40S, heures ouvrées | 426,40 € | instance 246,40 €, exploitation 180,00 € | — | 6 529 |
| GPU loué L40S, 24 h/24 | 1 202,00 € | instance 1 022,00 €, exploitation 180,00 € | — | 27 082 |
| GPU loué H100, 24 h/24 | 2 172,90 € | instance 1 992,90 €, exploitation 180,00 € | — | 105 162 |
| API Claude Haiku 5.5 | 62,13 € | exploitation 60,00 € | tokens 2,13 € | illimitée |
| API Claude Sonnet 5.5 | 102,67 € | exploitation 60,00 € | tokens 42,67 € | illimitée |
| API Claude Opus 5.5 | 145,35 € | exploitation 60,00 € | tokens 85,35 € | illimitée |

## 3. Points morts

| Comparé au poste local | Résultat |
|---|---|
| GPU loué L40S, heures ouvrées | le poste local est moins cher jusqu'à 149 333 runs/mois (au-delà de la capacité du poste : sans effet pratique) |
| GPU loué L40S, 24 h/24 | le poste local est moins cher jusqu'à 981 526 runs/mois (au-delà de la capacité du poste : sans effet pratique) |
| GPU loué H100, 24 h/24 | le poste local est moins cher jusqu'à 2 023 269 runs/mois (au-delà de la capacité du poste : sans effet pratique) |
| API Claude Haiku 5.5 | le poste local devient moins cher au-delà de 189 076 runs/mois (au-delà de la capacité du poste : sans effet pratique) |
| API Claude Sonnet 5.5 | le poste local devient moins cher au-delà de 5 443 runs/mois |
| API Claude Opus 5.5 | le poste local devient moins cher au-delà de 2 692 runs/mois |

## 4. Sensibilité (coût par run à 1 000 runs/mois)

**Prix de l'électricité** (valeur de base : 0,1624)

| Facteur | Poste local (RTX 4070 SUPER) | GPU loué L40S, 24 h/24 | API Claude Haiku 5.5 | API Claude Sonnet 5.5 | API Claude Opus 5.5 |
|---|---|---|---|---|---|
| ×0,5 | 0,288 € | 1,20 € | 0,062 € | 0,103 € | 0,145 € |
| ×1,0 | 0,288 € | 1,20 € | 0,062 € | 0,103 € | 0,145 € |
| ×2,0 | 0,289 € | 1,20 € | 0,062 € | 0,103 € | 0,145 € |

**Prix du poste** (valeur de base : 1700,0)

| Facteur | Poste local (RTX 4070 SUPER) | GPU loué L40S, 24 h/24 | API Claude Haiku 5.5 | API Claude Sonnet 5.5 | API Claude Opus 5.5 |
|---|---|---|---|---|---|
| ×0,5 | 0,265 € | 1,20 € | 0,062 € | 0,103 € | 0,145 € |
| ×1,0 | 0,288 € | 1,20 € | 0,062 € | 0,103 € | 0,145 € |
| ×2,0 | 0,335 € | 1,20 € | 0,062 € | 0,103 € | 0,145 € |

**Coût horaire d'exploitation** (valeur de base : 60,0)

| Facteur | Poste local (RTX 4070 SUPER) | GPU loué L40S, 24 h/24 | API Claude Haiku 5.5 | API Claude Sonnet 5.5 | API Claude Opus 5.5 |
|---|---|---|---|---|---|
| ×0,5 | 0,168 € | 1,11 € | 0,032 € | 0,073 € | 0,115 € |
| ×1,0 | 0,288 € | 1,20 € | 0,062 € | 0,103 € | 0,145 € |
| ×2,0 | 0,528 € | 1,38 € | 0,122 € | 0,163 € | 0,205 € |

**Heures d'exploitation du poste local par mois** (valeur de base : 4,0)

| Facteur | Poste local (RTX 4070 SUPER) | GPU loué L40S, 24 h/24 | API Claude Haiku 5.5 | API Claude Sonnet 5.5 | API Claude Opus 5.5 |
|---|---|---|---|---|---|
| ×0,5 | 0,168 € | 1,20 € | 0,062 € | 0,103 € | 0,145 € |
| ×1,0 | 0,288 € | 1,20 € | 0,062 € | 0,103 € | 0,145 € |
| ×2,0 | 0,528 € | 1,20 € | 0,062 € | 0,103 € | 0,145 € |

**Taux USD → EUR** (valeur de base : 0,86)

| Facteur | Poste local (RTX 4070 SUPER) | GPU loué L40S, 24 h/24 | API Claude Haiku 5.5 | API Claude Sonnet 5.5 | API Claude Opus 5.5 |
|---|---|---|---|---|---|
| ×0,5 | 0,288 € | 1,20 € | 0,061 € | 0,081 € | 0,103 € |
| ×1,0 | 0,288 € | 1,20 € | 0,062 € | 0,103 € | 0,145 € |
| ×2,0 | 0,288 € | 1,20 € | 0,064 € | 0,145 € | 0,231 € |

## 5. Hypothèses et leur origine

| Hypothèse | Valeur | Statut | Origine |
|---|---|---|---|
| `electricity_eur_per_kwh` | 0,1624 | sourcé | Tarif Bleu Pro, ~0,1624 EUR/kWh HT (Selectra, août 2026) ; les sources divergent (0,25 EUR/kWh HT pour les petits professionnels au S1 2026) |
| `host_power_w` | 120,0 | hypothèse à valider | Puissance du poste hors GPU pendant un run, non mesurée |
| `workstation_capex_eur` | 1700,0 | hypothèse à valider | 659 EUR TTC pour la carte au lancement + ~1 000 EUR pour le reste ; prix actuels non vérifiés (hausse des GPU signalée en 2026) |
| `amortization_months` | 36 | hypothèse à valider | Durée d'amortissement comptable usuelle d'un poste |
| `l40s_eur_per_hour` | 1,4 | sourcé | Scaleway, tarif public L40S, à l'heure |
| `h100_eur_per_hour` | 2,73 | sourcé | Scaleway, tarif public H100, à l'heure |
| `l40s_speedup` | 1,71 | estimé | Rapport des bandes passantes mémoire, pas une mesure |
| `h100_speedup` | 6,64 | estimé | Rapport des bandes passantes mémoire, pas une mesure |
| `office_hours_per_month` | 176,0 | hypothèse à valider | Instance allumée 8 h par jour ouvré |
| `usd_to_eur` | 0,86 | hypothèse à valider | Taux de change de travail, à remplacer par le taux du jour |
| `ops_hours_onprem` | 4,0 | hypothèse à valider | Mises à jour de modèles, pilotes, supervision ; à calibrer sur l'exploitation réelle |
| `ops_hours_cloud_gpu` | 3,0 | hypothèse à valider | Idem on-premise, plus l'instance à administrer |
| `ops_hours_api` | 1,0 | hypothèse à valider | Suivi des versions de modèles et de la facture |
| `ops_eur_per_hour` | 60,0 | hypothèse à valider | Coût horaire chargé d'un ingénieur, à remplacer |
| `utilization` | 0,5 | hypothèse à valider | Un run à la fois, jamais plus de la moitié du temps |

Prix API ($ par million de tokens, prompt ≤ 100 K) : Claude Haiku 5.5 0,1/0,5 ; Claude Sonnet 5.5 2,0/10,0 ; Claude Opus 5.5 4,0/20,0 (platform.claude.com, vérifié le 05/11/2026).

