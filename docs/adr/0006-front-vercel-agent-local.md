# 0006 · Front sur Vercel, agent sur le poste GPU

**Contexte.** Un démonstrateur en ligne gratuit est demandé. Vercel est serverless : ni GPU,
ni Docker, durées limitées.

**Décision.** Le front Next.js est déployé sur Vercel ; l'API, les modèles et le sandbox
restent sur le poste GPU, exposés par un tunnel HTTPS protégé par un jeton.

**Conséquences.** Rien d'autre que du texte ne transite par Vercel. Le poste doit être
allumé pendant la démo et l'URL du tunnel change à chaque lancement (`scripts/demo.sh`).
En production, l'agent irait sur une machine GPU dédiée.
