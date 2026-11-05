# 0004 · Deux étages reliés par un contrat JSON

**Contexte.** Wavestone a demandé deux étages testables et évaluables indépendamment.

**Décision.** L'étage 1 produit des `Artifact` (table, figure, constat) ; l'étage 2 les lit
et ne voit jamais les données ni le code. Streamlit, le front et un futur rapport Word/PDF
sont des rendus du même JSON.

**Conséquences.** On compare des modèles de rédaction à artefacts identiques. Modifier le
contrat touche les deux côtés : à signaler dans la PR.
