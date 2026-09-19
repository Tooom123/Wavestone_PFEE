# data/

Repertoire des jeux de donnees locaux. **Aucun CSV n'est versionne** (decision Wavestone,
cf. conventions de depot) : `.gitignore` exclut `data/` a l'exception de ce README.

## Recuperer les donnees

```bash
uv run python scripts/download_data.py
```

Le script telecharge les datasets dans `data/<nom_du_dataset>/`.

## Criteres de selection des datasets

Cible : 3 a 4 jeux de donnees a la fois **riches** (volume et variete de colonnes suffisants
pour porter de vraies questions metier) et **techniquement simples** (CSV propre, pas de
preparation lourde qui bloquerait le demarrage).
