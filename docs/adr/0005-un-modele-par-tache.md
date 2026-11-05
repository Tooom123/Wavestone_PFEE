# 0005 · Un modèle par tâche

**Contexte.** Le modèle qui code le mieux n'est pas celui qui rédige le mieux : qwen-coder
a écrit « 42,7 % des départements » et inventé une marge qu'aucun artefact ne contenait.

**Décision.** Plan et réponse : `gemma4:e4b`. Code et critique : `qwen2.5-coder:14b`.
Choix mesurés avec `scripts/bench_models.py` sur des entrées identiques.

**Conséquences.** Chaque changement de modèle coûte 11 à 32 s de chargement ; garder le même
pour le code et la critique évite un rechargement. Tout changement de version de modèle doit
repasser par l'évaluation avant d'être adopté.
