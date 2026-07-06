# Overview

SimParc-R Simulator runs large-scale residential building stock simulations using an OpenStudio-HPXML workflow.

## What it does

1. Reads a building stock CSV.
2. Validates and preprocesses inputs against HPXML argument constraints.
3. Optionally applies upgrade scenarios defined in `project.yaml`.
4. Runs simulations in parallel through OpenStudio.
5. Generates structured outputs for downstream analysis.

## Main project modules

- `local.py`: main command-line entry point.
- `project.yaml`: simulation configuration.
- `preprocessing.py`: input data preprocessing.
- `upgrading.py`: upgrade filters and transformations.
- `building.py`: per-building workflow generation.
- `postprocessing.py`: post-processing and output datasets.

## Typical workflow

1. Configure project parameters in `project.yaml`.
2. Run a batch simulation.
3. Inspect output datasets in `results/`.
