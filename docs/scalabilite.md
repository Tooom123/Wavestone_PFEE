# Passage à l'échelle : jeux de plusieurs Go

Point (d) de la réunion du 23/10 : *étudier la scalabilité sur des jeux de plusieurs Go (CSV, SQL,
gros volumes), l'impact sur l'infrastructure et les coûts.*

## Ce qui grossit, ce qui ne grossit pas

| Partie de l'agent | Dépend de la taille des données ? |
|---|---|
| Appels au LLM (plan, code, critique, synthèse) | **Non.** Le LLM ne voit que le profil : une ligne par colonne, quelle que soit la longueur du fichier. Le coût en tokens et en GPU d'un run ne change pas avec le volume. |
| Profilage | Oui : il lit tout le fichier. |
| Exécution du code généré | Oui : c'est elle qui touche aux données, dans un sandbox limité à **2 Go de mémoire et 2 cœurs**. |

Le risque n'est donc pas le coût du LLM : c'est que le profilage devienne lent, et surtout que le
code généré **dépasse la mémoire du sandbox** et soit tué.

## Mesures

`scripts/bench_scale.py` fabrique des CSV de taille croissante en répétant Superstore, puis mesure
chaque opération dans un processus neuf (durée, mémoire maximale). Résultats bruts :
[`scalabilite-mesures.json`](scalabilite-mesures.json). Poste de 28 cœurs et 15 Go de RAM ; les
agrégations DuckDB sont limitées à 2 cœurs, comme dans le sandbox.

| Opération | 0,25 Go (1,2 M lignes) | 1 Go (4,6 M lignes) | Tient dans les 2 Go du sandbox à 1 Go ? |
|---|---|---|---|
| Profilage pandas (avant) | 20 s · 836 Mo | 79 s · **2 953 Mo** | — (hors sandbox, mais 3 Go de RAM) |
| **Profilage DuckDB (maintenant)** | 4 s · 933 Mo | **6 s** · 1 334 Mo | — |
| Calcul type, pandas sur tout le fichier | 2,1 s · 827 Mo | 7,9 s · **2 927 Mo** | **non : le code serait tué** |
| Calcul type, pandas sur 2 colonnes (`usecols`) | 1,1 s · 261 Mo | 3,7 s · 687 Mo | oui |
| **Calcul type, DuckDB (2 cœurs)** | 0,3 s · 207 Mo | **0,9 s · 249 Mo** | oui |
| Même calcul sur Parquet (DuckDB) | 0,06 s · 69 Mo | 0,07 s · 71 Mo | oui |

*Calcul type : chiffre d'affaires par année, l'opération la plus fréquente du golden dataset.*

**Lecture.** pandas occupe environ **2,9 fois la taille du fichier** en mémoire : le code que
l'agent écrivait jusqu'ici (`pd.read_csv` du fichier entier) dépasse le sandbox dès ~0,7 Go de
CSV. DuckDB parcourt le fichier sans le charger : sa mémoire reste autour de 250 Mo, et sa durée
croît d'environ 1 s par Go sur 2 cœurs.

**Extrapolation à 10 Go** (linéaire, *non mesurée*, faute de disque sur le poste) : pandas
demanderait ~29 Go de RAM ; `usecols` ~7 Go (selon le nombre de colonnes lues) ; DuckDB quelques
centaines de Mo et ~10 s. Le profilage DuckDB passerait à une quarantaine de secondes, contre
~13 min et ~30 Go pour pandas.

## Ce qui a changé dans l'agent

1. **Profilage sans chargement.** Au-delà de 200 Mo (`LARGE_FILE_MB`), `profile_csv` passe par
   DuckDB : nombre de lignes, valeurs manquantes, bornes, moyennes, quantiles et période des dates
   sur **tout** le fichier, en une passe parallèle ; nature des colonnes et modalités sur un
   échantillon aléatoire de 100 000 lignes. Sur les trois jeux du projet, le profil obtenu est
   identique à celui de pandas (types, dates, valeurs manquantes, moyennes). Le nombre de valeurs
   distinctes et les quantiles sont approchés. Le profil indique comment il a été calculé
   (`profiling`) et la taille du fichier (`size_mb`).
2. **Consigne au générateur de code.** Pour un fichier volumineux, le prompt indique sa taille et
   interdit de le charger entier avec pandas : agrégation en SQL avec DuckDB, ou échantillon des
   seules colonnes utiles quand pandas est nécessaire (modèle, test). Le SQL d'exemple du prompt a
   été vérifié sur le vrai fichier Superstore.
3. **DuckDB 1.5.5 dans le sandbox** (au lieu de 1.1.3), la même version que l'agent : elle lit en
   mode tolérant (`strict_mode=false`) les CSV non conformes, comme Superstore et ses fins de ligne
   CR, que la lecture stricte refuse.

## Impact sur l'infrastructure et les coûts

- **Pas de machine plus grosse pour quelques Go.** Avec DuckDB, le sandbox de 2 Go suffit ; avec
  pandas, il faudrait ~3 Go de RAM par Go de données, par run.
- **Le coût d'un run ne bouge presque pas.** Il est dominé par le LLM (`docs/finops/`), qui ne
  dépend pas du volume. Le calcul sur les données ajoute de l'ordre d'une seconde par Go, à
  comparer aux ~50 à 80 s d'un run.
- **Le stockage devient le premier poste.** Un jeu de 10 Go en CSV occupe 10 Go sur le poste ;
  converti en Parquet, nettement moins (×9 sur nos données répétées, qui se compressent
  anormalement bien : à mesurer sur de vraies données) et il se lit plus vite.
- **Au-delà de quelques dizaines de Go**, la limite devient le disque et les entrées-sorties d'un
  seul poste. C'est le point où le calcul doit aller vers la plateforme de données plutôt que les
  données vers l'agent.

## Sources SQL et data platform

L'agent lit aujourd'hui des fichiers. Pour une base ou un entrepôt, deux patterns, du plus simple au
plus intégré :

1. **Extraction en Parquet** : la plateforme exporte la table ou la vue utile en Parquet, l'agent
   la lit comme un fichier. Aucun changement de l'agent ; adapté au POC et aux volumes moyens.
2. **Calcul poussé dans l'entrepôt** : le profil est calculé par des requêtes d'agrégation sur la
   table (même principe que `SUMMARIZE`), le LLM génère du SQL au lieu de Python, et l'entrepôt
   l'exécute. Les garde-fous du sandbox changent de forme : compte en lecture seule, délai maximal
   par requête, limite de lignes renvoyées. Le principe « le LLM ne voit que le profil » reste
   identique.

Le choix dépend des plateformes et abonnements existants chez Wavestone (point f de la réunion).

## Limites

- Les fichiers de test répètent Superstore : la compression Parquet est surestimée, et la
  distribution des valeurs n'est pas celle d'un vrai jeu de plusieurs Go.
- **Run complet de l'agent sur un CSV d'1 Go (15/11/2026)** : profil DuckDB des 4,6 M lignes, code
  généré qui agrège avec DuckDB sans charger le fichier, réussi à la 2e tentative (une erreur
  corrigée par la boucle), 49 s au total. Chiffres justes (2012 : 2 042 260 160, identique au
  benchmark). Mais la synthèse a ajouté une phrase sur « 2017 et 2018 », années absentes des
  données : un défaut de l'étage 2, sans lien avec le volume, à surveiller.
- Extrapolation à 10 Go : linéaire, non mesurée.
