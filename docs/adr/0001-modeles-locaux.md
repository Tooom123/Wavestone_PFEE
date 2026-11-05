# 0001 · Modèles de langage locaux

**Contexte.** Les données clients ne doivent pas quitter l'entreprise, et les coûts d'API
sont imprévisibles. Wavestone a validé l'approche locale sur GPU (réunion du 23/10/2026).

**Décision.** Les modèles tournent en local via Ollama. Un fournisseur distant reste possible
derrière `LLMClient`, mais n'est pas implémenté.

**Conséquences.** Rien ne sort du poste, coût marginal nul. En contrepartie : un GPU, une
qualité de génération de code en retrait des modèles frontière, et un suivi des versions de
modèles à organiser (voir le benchmark de coûts et de maintenabilité).
