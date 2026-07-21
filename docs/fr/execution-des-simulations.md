# Exécution des simulations

## Lancer un lot complet

```bash
uv run local.py project.yaml
```

## Ce qui se passe pendant l'exécution

1. La configuration YAML est chargée et validée.
2. Les données d'entrée sont prétraitées et transformées.
3. Les scénarios de mesures sont appliqués si configurés.
4. Chaque bâtiment reçoit son dossier de simulation et son fichier OSW.
5. Les simulations OpenStudio sont exécutées en parallèle.
6. Les sorties sont collectées et post-traitées.

## Dépannage de base

- Si OpenStudio est introuvable, vérifier `OPENSTUDIO_EXE` ou `PATH`.
- Si la validation schéma échoue, vérifier `SCHEMA_VERSION` et les champs requis.
- Si la correspondance météo échoue, vérifier les noms de région et les options météo.
