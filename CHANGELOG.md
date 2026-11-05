# Changelog

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), versions [SemVer](https://semver.org/lang/fr/).

## [Non publié]

### Retiré
- Modèles de PR et d'issues, fichier CODEOWNERS, notification par mail

### Ajouté
- Benchmark coûts on-premise contre cloud (`docs/finops/`, `agent_data.finops`, `scripts/finops_report.py`)

## [0.2.0] - 2026-11-05

### Ajouté
- Métriques par run : tokens par agent, énergie du GPU (Wh), durée hors attente de validation
- Catalogue de GPU et endpoint `/api/system`
- Front : bloc « Le matériel » (GPU en direct, comparaison) et coût de chaque run
- Pipeline CI/CD : qualité, tests avec couverture, sécurité, Docker, front (`.github/workflows/`)
- Publication de l'image du sandbox sur GHCR à chaque tag
- Branches `develop` et `feature/*`, ouverture automatique des PR, release PR
- Typage mypy, analyse bandit, audit des dépendances, hooks pre-commit, Makefile
- Documentation du workflow Git et de la CI/CD (`docs/`)

### Corrigé
- Validation du schéma de l'URL du LLM (`http` ou `https` uniquement)
- Failles de `pillow` (via Streamlit 1.66)

## [0.1.0] - 2026-10-23

### Ajouté
- Agent d'analyse de bout en bout : profil, plan, code, sandbox, critique, réponse
- Un modèle local par tâche (plan et réponse : gemma4 ; code et critique : qwen2.5-coder)
- API FastAPI et front Next.js déployé sur Vercel, validation humaine du plan
- Évaluation par étage et benchmark des modèles
