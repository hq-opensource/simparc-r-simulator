# Execution des simulations

## Lancer un lot complet

```bash
uv run local.py project.yaml
```

## Lancer seulement le post-traitement

```bash
uv run local.py project.yaml --postprocessonly
```

## Ce qui se passe pendant l'execution

1. La configuration YAML est chargee et validee.
2. Les donnees d'entree sont pretraitees et transformees.
3. Les scenarios de mesures sont appliques si configures.
4. Chaque batiment recoit son dossier de simulation et son fichier OSW.
5. Les simulations OpenStudio sont executees en parallele.
6. Les sorties sont collectees et post-traitees.

## Depannage de base

- Si OpenStudio est introuvable, verifier `OPENSTUDIO_EXE` ou `PATH`.
- Si la validation schema echoue, verifier `SCHEMA_VERSION` et les champs requis.
- Si la correspondance meteo echoue, verifier les noms de region et les options meteo.
