# Configuration

The simulator behavior is driven by `project.yaml`.

## Key settings

- `SCHEMA_VERSION`: schema version used for YAML validation.
- `SAMPLE_FILE`: input CSV listing the buildings to simulate.
- `HPXML_SCHEMA_FILE`: XML schema source used to extract argument constraints.
- `N_JOBS`: number of parallel workers.
- `SIMULATION_TIMESTEP`, `SIMULATION_YEAR`, `SIMULATION_RUN_PERIOD`.
- `WEATHER_FILE_TYPE`: weather mapping mode (`AMY`, `CWEC`, `PCIC`).
- `BATCH_MODE`: controls immediate post-processing and cleanup behavior.

## Upgrade scenarios

Use `UPGRADES_SETTINGS` to define named sets with:

- `Filters` using `all`, `any`, and `not` logic.
- `Adoption rate`.
- One or more `Upgrades` with parameters.

## Example launch setup

Before running a batch, verify:

1. `project.yaml` points to the correct input CSV.
2. OpenStudio executable is available.
3. Weather files and mapping are present for the selected simulation year and weather mode.
