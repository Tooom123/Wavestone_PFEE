# Sécurité

## Signaler une vulnérabilité

Ne pas ouvrir d'issue publique. Écrire à l'équipe projet (contact dans le README) en décrivant
le problème et comment le reproduire. Réponse sous 5 jours ouvrés.

## Ce que le projet garantit, et comment c'est vérifié

| Garantie | Mécanisme | Vérification |
|---|---|---|
| Le LLM ne voit jamais les données | Seul le profil (schéma, statistiques) entre dans son contexte ; erreurs et identifiants masqués | `tests/test_critic.py`, `tests/test_rendering.py` |
| Le code généré ne touche pas l'hôte | Conteneur sans réseau, racine en lecture seule, utilisateur non privilégié, quotas | `tests/test_sandbox.py` (exécutés en CI) |
| Sans Docker, rien ne s'exécute | Aucun repli sur l'hôte | `tests/test_sandbox.py` |
| Pas de secret ni de donnée dans le dépôt | `.gitignore`, hook pre-commit, `gitleaks` en CI | job « Sécurité » |
| Dépendances saines | `pip-audit`, `npm audit`, Dependabot | job « Sécurité » |

## API de démonstration

Protégée par un jeton (`API_TOKEN`), CORS restreint, jeux de données connus seulement,
un seul run à la fois. Ne jamais l'exposer sans jeton.
