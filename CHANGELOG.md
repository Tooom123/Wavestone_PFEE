# Changelog

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), versions [SemVer](https://semver.org/lang/fr/).

## [Non publié]

### Ajouté
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
