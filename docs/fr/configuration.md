# Configuration

Le comportement du simulateur est piloté par `project.yaml`.

## Paramètres importants

- `SCHEMA_VERSION`: version du schéma pour la validation YAML.
- `SAMPLE_FILE`: fichier CSV d'entrée listant les bâtiments à simuler.
- `HPXML_SCHEMA_FILE`: source XML utilisée pour extraire les contraintes d'arguments.
- `N_JOBS`: nombre de workers parallèles.
- `SIMULATION_TIMESTEP`, `SIMULATION_YEAR`, `SIMULATION_RUN_PERIOD`.
- `WEATHER_FILE_TYPE`: mode de correspondance météo (`AMY`, `CWEC`, `PCIC`).
- `BATCH_MODE`: contrôle le post-traitement et le nettoyage immédiats.

## Scénarios de mesures

`UPGRADES_SETTINGS` permet de définir des ensembles nommés avec:

- des `Filters` avec logique `all`, `any`, `not`;
- un `Adoption rate`;
- une ou plusieurs `Upgrades` paramétrées.

## Vérification avant lancement

1. Vérifier que `project.yaml` pointe vers le bon CSV d'entrée.
2. Vérifier la disponibilité de l'exécutable OpenStudio.
3. Vérifier la présence des fichiers météo et de leur correspondance.
