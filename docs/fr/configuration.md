# Configuration

Le comportement du simulateur est pilote par `project.yaml`.

## Parametres importants

- `SCHEMA_VERSION`: version du schema pour la validation YAML.
- `SAMPLE_FILE`: fichier CSV d'entree listant les batiments a simuler.
- `HPXML_SCHEMA_FILE`: source XML utilisee pour extraire les contraintes d'arguments.
- `N_JOBS`: nombre de workers paralleles.
- `SIMULATION_TIMESTEP`, `SIMULATION_YEAR`, `SIMULATION_RUN_PERIOD`.
- `WEATHER_FILE_TYPE`: mode de correspondance meteo (`AMY`, `CWEC`, `PCIC`).
- `BATCH_MODE`: controle le post-traitement et le nettoyage immediats.

## Scenarios de mesures

`UPGRADES_SETTINGS` permet de definir des ensembles nommes avec:

- des `Filters` avec logique `all`, `any`, `not`;
- un `Adoption rate`;
- une ou plusieurs `Upgrades` parametrees.

## Verification avant lancement

1. Verifier que `project.yaml` pointe vers le bon CSV d'entree.
2. Verifier la disponibilite de l'executable OpenStudio.
3. Verifier la presence des fichiers meteo et de leur correspondance.
