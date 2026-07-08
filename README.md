# SimParc-R Simulator

<p align="center">
	<img src="docs/figures/logo.png" alt="SimParc-R logo" width="180">
</p>

La première section est en français et la documentation complète est [ici](https://hq-opensource.github.io/simparc-r-simulator/).  
  
English is following and full documentation is [here](https://hq-opensource.github.io/simparc-r-simulator/).

## Français

### Aperçu

SimParc-R Simulator permet d'exécuter des simulations de parcs résidentiels à grande échelle à partir du flux OpenStudio-HPXML du NLR. Le dépôt lit un fichier CSV de bâtiments, valide et transforme les entrées, applique au besoin des scénarios de mesures, lance les simulations OpenStudio en parallèle, puis génère des sorties post-traitées prêtes pour l'analyse.

Caractéristiques principales:

- Procédure de simulation basé sur OpenStudio-HPXML.
- Exécution parallèle sur un grand nombre de bâtiments.
- Scénarios de mesures pilotés par filtres et taux d'adoption.
- Profils stochastiques pour certains usages (ex. VE, piscine, spa, consigne de chauffage).
- Sorties structurées pour métadonnées, séries temporelles et erreurs.

### Structure du dépôt

Fichiers et modules principaux:

- `local.py`: point d'entrée CLI et orchestration du lot complet.
- `project.yaml`: configuration de simulation (échantillon, météo, sorties, mesures, etc.).
- `base.py`: classe de base et fonctions utilitaires de nettoyage des dossiers de simulation.
- `preprocessing.py`: typage des colonnes, validation alignée HPXML, conversion en dictionnaires par bâtiment.
- `upgrading.py`: moteur de filtres et application des mesures.
- `building.py`: génération du workflow par bâtiment et des profils stochastiques.
- `postprocessing.py`: extraction et écriture des résultats annuels/temporels/erreurs.
- `hpxml_input_schema.py`: extraction des contraintes d'arguments HPXML à partir de `measure.xml`.
- `measures/`: mesures OpenStudio appelées dans les OSW (OpenStudio Workflow).
- `schemas/`: versions de schéma YAML pour la validation du fichier projet.
- `weather/`: fichiers météo et tables de correspondance.
- `results/`: artefacts de simulation et jeux de données post-traités.

### Flux de traitement

1. Chargement et validation de `project.yaml` avec `schemas/v{SCHEMA_VERSION}.yaml`.
2. Lecture du CSV (`SAMPLE_FILE`) et prétraitement des types selon les contraintes HPXML.
3. Application des ensembles de mesures (`UPGRADES_SETTINGS`).
4. Construction des entrées de simulation par bâtiment (arguments HPXML et non-HPXML).
5. Pour chaque bâtiment:
	 - Création du dossier de simulation et du JSON de métadonnées.
	 - Génération optionnelle de profils stochastiques.
	 - Génération du `in.osw`.
	 - Exécution d'OpenStudio CLI.
	 - Lecture des sorties puis post-traitement/nettoyage immédiat en mode batch.
6. Écriture du résumé global (`results/results_job0.json.gz`).
7. Production des jeux parquet partitionnés (metadata, timeseries, errors).

### Prérequis

- Python 3.11+
- OpenStudio SDK 3.9.0
- Un des environnements suivants:
	- Environnement local Python géré avec UV
	- Dev Container (Docker + extension Dev Containers)

Les dépendances Python sont définies dans `pyproject.toml`.

### Installation

#### Option A: UV + SDK OpenStudio local

1. Installer UV: https://docs.astral.sh/uv/getting-started/installation/
2. Installer OpenStudio SDK 3.9.0: https://github.com/NREL/OpenStudio/releases/tag/v3.9.0
3. Cloner ce dépôt.
4. Installer les dépendances:

```bash
uv sync
```

5. Rendre OpenStudio accessible:
	 - Recommandé: définir `OPENSTUDIO_EXE` avec le chemin absolu vers l'exécutable comme variable d'environnement.
	 - Alternative: ajouter le dossier `bin` d'OpenStudio au `PATH`.

Exemple (PowerShell):

```powershell
$env:OPENSTUDIO_EXE = "C:\path\to\OpenStudio-3.9.0\bin\openstudio.exe"
```

#### Option B: Dev Container

1. Installer Docker.
2. Installer VS Code.
3. Installer l'extension Dev Containers.
4. Ouvrir le dépôt dans le conteneur de développement fourni.

Dans ce mode, le runtime détecte `AM_I_IN_A_DOCKER_CONTAINER` et utilise directement `openstudio`.

### Démarrage rapide

Lancer un lot complet:

```bash
uv run local.py project.yaml
```

### Configuration (`project.yaml`)

Champs importants:

- `SCHEMA_VERSION`: sélection du schéma de validation dans `schemas/`.
- `SAMPLE_FILE`: chemin vers le fichier CSV listant les bâtiments à simuler.
- `HPXML_SCHEMA_FILE`: chemin vers le XML de mesure utilisé pour déduire les contraintes HPXML.
- `N_JOBS`: nombre de workers parallèles. Si omis, valeur par défaut = nombre de CPU moins 8.
- `SIMULATION_TIMESTEP`, `SIMULATION_YEAR`, `SIMULATION_RUN_PERIOD`.
- `WEATHER_FILE_TYPE`: mode de correspondance météo (ex. AMY, CWEC, PCIC).
- `BATCH_MODE`: contrôle le post-traitement/nettoyage immédiat par bâtiment.
- Commutateurs de sortie (`INCLUDE_ANNUAL_*`, `INCLUDE_TIMESERIES_*`, etc.).
- `UPGRADES_SETTINGS`: ensembles nommés avec:
	- `Filters` (`all`, `any`, `not`)
	- `Adoption rate`
	- Paramètres de `Upgrades`

### Entrées et sorties

Entrées typiques:

- CSV de parc de bâtiments (colonnes HPXML et non-HPXML).
- Fichier de configuration projet.
- Fichiers EPW et correspondances météo.

Sorties typiques dans `results/`:

- Dossiers par bâtiment (journaux, artefacts de workflow, intermédiaires optionnels).
- `results_job0.json.gz`: résumé compact par simulation.
- `metadata.parquet/`: métadonnées partitionnées par bâtiment.
- `timeseries.parquet/`: séries temporelles partitionnées (si activées).
- `errors.parquet/`: échecs avec statut et message.

### Syntaxe des filtres de mesures

Opérateurs supportés:

- `==`, `!=`, `>`, `<`, `>=`, `<=`, `in`, `not in`

Structures logiques:

- `{"all": [...]}`: ET logique
- `{"any": [...]}`: OU logique
- `{"not": [...]}`: NON logique sur un groupe de conditions

Format d'une condition atomique:

```yaml
["nom_colonne", "operateur", valeur]
```

### Notes et limites

- Le point d'entrée actuel est `local.py`.
- Le parallélisme est géré via Joblib selon la configuration interne.
- La résolution du chemin OpenStudio suit l'ordre:
	1. `OPENSTUDIO_EXE`
	2. `openstudio` trouvé dans le `PATH`
- Les gros lots peuvent produire un volume important de données dans `results/`.

### Dépannage

- OpenStudio introuvable:
	- Vérifier `OPENSTUDIO_EXE` ou le `PATH`.
- Erreur de schéma:
	- Vérifier que `SCHEMA_VERSION` pointe vers un fichier présent dans `schemas/`.
- Fichier météo manquant:
	- Vérifier `WEATHER_FILE_TYPE`, `SIMULATION_YEAR` et les noms de région dans le CSV.
- Sorties vides ou partielles:
	- Inspecter `openstudio_output.log` et les statuts en sortie post-traitée.

### Outil connexe

Le fichier CSV listant les bâtiments du parc à simuler peut être préparé grâce au code du dépôt GitHub dédié à l'échantillonneur ici:

- https://github.com/hq-opensource/simparc-r-sampler

### Contribution

1. Créer une branche de fonctionnalité.
2. Garder les changements de configuration explicites et reproductibles.
3. Valider sur un petit échantillon avant un gros lot.
4. Ouvrir une PR avec contexte, hypothèses et preuves de test.

### Licence

Voir `LICENSE`.

---

## English

### Overview

SIMPARC-R Simulator runs large-scale residential building stock simulations based on the NLR OpenStudio-HPXML workflow. It reads a building stock CSV file, validates and transforms inputs, optionally applies upgrade scenarios, runs OpenStudio simulations in parallel, then generates post-processed outputs ready for analysis.

Key characteristics:

- OpenStudio-HPXML based simulation pipeline.
- Parallel execution for many buildings.
- Rule-based upgrade scenarios (filters + adoption rates).
- Stochastic profiles for selected end uses (e.g., EV, pool, spa, heating setpoint).
- Structured outputs for metadata, timeseries, and errors.

### Repository Structure

Main entry points and modules:

- `local.py`: command-line entry point and orchestration of the full batch workflow.
- `project.yaml`: simulation configuration (input sample, weather mode, output options, upgrades, etc.).
- `base.py`: shared batch base class and simulation directory cleanup helpers.
- `preprocessing.py`: input casting, schema-aligned validation logic, and conversion to per-building dictionaries.
- `upgrading.py`: filter engine and upgrade application logic.
- `building.py`: per-building workflow generation and stochastic profile generation.
- `postprocessing.py`: extraction and write-out of annual/timeseries/error outputs.
- `hpxml_input_schema.py`: extraction of HPXML argument constraints from `measure.xml`.
- `measures/`: OpenStudio measures used in generated OSW (OpenStudio Workflow) files.
- `schemas/`: YAML schema versions for project file validation.
- `weather/`: weather files and mappings used during simulation setup.
- `results/`: simulation artifacts and post-processed datasets.

### End-to-End Workflow

1. Load and validate project configuration (`project.yaml`) against `schemas/v{SCHEMA_VERSION}.yaml`.
2. Read building stock CSV (`SAMPLE_FILE`) and preprocess data types according to HPXML argument constraints.
3. Apply upgrade sets defined in `UPGRADES_SETTINGS` (filters + adoption rates).
4. Build per-building simulation inputs (HPXML args + non-HPXML args).
5. For each building:
	 - Create simulation folder and metadata JSON.
	 - Generate optional stochastic profiles.
	 - Generate `in.osw` (OpenStudio workflow).
	 - Run OpenStudio CLI.
	 - Read simulation outputs and optionally post-process/cleanup immediately in batch mode.
6. Write global run summary (`results/results_job0.json.gz`).
7. Generate partitioned parquet datasets (metadata, timeseries, errors) during post-processing.

### Requirements

- Python 3.11+
- OpenStudio SDK 3.9.0
- One of:
	- Local Python environment managed with UV
	- Dev Container environment (Docker + VS Code Dev Containers)

Python dependencies are declared in `pyproject.toml`.

### Installation

#### Option A: UV + local OpenStudio SDK

1. Install UV: https://docs.astral.sh/uv/getting-started/installation/
2. Install OpenStudio SDK 3.9.0: https://github.com/NREL/OpenStudio/releases/tag/v3.9.0
3. Clone this repository.
4. Sync dependencies:

```bash
uv sync
```

5. Make OpenStudio available:
	 - Preferred: set `OPENSTUDIO_EXE` to the full executable path.
	 - Alternative: add OpenStudio `bin` to your `PATH`.

Example (PowerShell):

```powershell
$env:OPENSTUDIO_EXE = "C:\path\to\OpenStudio-3.9.0\bin\openstudio.exe"
```

#### Option B: Dev Container

1. Install Docker.
2. Install VS Code.
3. Install the Dev Containers extension.
4. Reopen this repository in the provided development container.

In container mode, the runtime checks `AM_I_IN_A_DOCKER_CONTAINER` and uses `openstudio` directly.

### Quick Start

Run a full simulation batch:

```bash
uv run local.py project.yaml
```

### Configuration (`project.yaml`)

Important fields include:

- `SCHEMA_VERSION`: selects the validation schema under `schemas/`.
- `SAMPLE_FILE`: path to the CSV file listing the buildings to simulate.
- `HPXML_SCHEMA_FILE`: path to measure XML used to infer HPXML constraints.
- `N_JOBS`: parallel workers. If omitted, defaults to CPU count minus 8.
- `SIMULATION_TIMESTEP`, `SIMULATION_YEAR`, `SIMULATION_RUN_PERIOD`.
- `WEATHER_FILE_TYPE`: weather mapping mode (e.g., AMY, CWEC, PCIC).
- `BATCH_MODE`: controls immediate post-process/cleanup behavior per building.
- Output switches (`INCLUDE_ANNUAL_*`, `INCLUDE_TIMESERIES_*`, etc.).
- `UPGRADES_SETTINGS`: named upgrade sets with:
	- `Filters` (`all`, `any`, `not` logic)
	- `Adoption rate`
	- `Upgrades` arguments

### Inputs and Outputs

Typical inputs:

- Building stock CSV with both HPXML-related and custom columns.
- Project configuration YAML.
- Weather file mappings and EPW files.

Typical outputs in `results/`:

- Per-building folders (logs, workflow artifacts, optional intermediate files).
- `results_job0.json.gz`: condensed per-simulation summary.
- `metadata.parquet/`: partitioned metadata by building.
- `timeseries.parquet/`: partitioned timeseries by building (if enabled).
- `errors.parquet/`: failures with status and messages.

### Upgrade Filter Syntax

Supported operators in filter conditions:

- `==`, `!=`, `>`, `<`, `>=`, `<=`, `in`, `not in`

Logical structures:

- `{"all": [...]}`: logical AND
- `{"any": [...]}`: logical OR
- `{"not": [...]}`: logical NOT on grouped conditions

Atomic condition format:

```yaml
["column_name", "operator", value]
```

### Notes and Limitations

- This repository currently runs through `local.py`.
- Parallelism currently uses Joblib backends configured in code.
- OpenStudio path resolution order is:
	1. `OPENSTUDIO_EXE`
	2. `openstudio` from system `PATH`
- Large batches can generate substantial disk usage in `results/`.

### Troubleshooting

- OpenStudio not found:
	- Verify `OPENSTUDIO_EXE` or `PATH`.
- Schema validation error:
	- Ensure `SCHEMA_VERSION` matches a file in `schemas/`.
- Missing weather mapping or EPW:
	- Check `WEATHER_FILE_TYPE`, `SIMULATION_YEAR`, and region naming in input CSV.
- Empty/partial outputs:
	- Inspect `openstudio_output.log` and per-building status in post-processed outputs.

### Related Tooling

The CSV file listing the buildings in the stock to simulate can be prepared using the dedicated sampler repository:

- https://github.com/hq-opensource/simparc-r-sampler

### Contributing

1. Create a feature branch.
2. Keep configuration changes explicit and reproducible.
3. Validate with a small sample before large batch runs.
4. Open a pull request with context, assumptions, and test evidence.

### License

See `LICENSE`.
  
