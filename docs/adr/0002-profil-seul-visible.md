# 0002 · Le LLM ne voit que le profil des données

**Contexte.** Confidentialité (RGPD), coût en tokens et limite de contexte.

**Décision.** Seul le `DatasetProfile` (schéma, types, cardinalités, statistiques agrégées)
entre dans le contexte. Les messages d'erreur et les identifiants des artefacts sont masqués
avant de revenir au modèle ; l'artefact stocké garde tout.

**Conséquences.** Deux fuites réelles ont été trouvées en run (valeur fautive citée par
pandas, colonne d'identifiants) puis fermées, avec des tests. Toute nouvelle information
envoyée au modèle doit passer par le profil.
