# Segmentation Simulation Workflow

This directory contains the configuration and workflow for running SimParc-R simulations on segmented building stocks.

## Directory Structure

```
Segmentation/
├── project.yaml                           # Base configuration (common parameters)
├── config/                                # Segment-specific configurations (auto-generated)
│   ├── project_Segment_001.yaml          # Segment 001 config
│   └── project_Segment_002.yaml          # Segment 002 config
├── segments/
│   ├── segment_Segment_001.csv           # Building stock for segment 001
│   └── segment_Segment_002.csv           # Building stock for segment 002
├── results/                              # All segment results
│   ├── Segment_001/                      # Segment 001 results
│   │   ├── 1/                            # Building 1
│   │   ├── 2/                            # Building 2
│   │   ├── ...
│   │   ├── results_job0.json.gz
│   │   ├── metadata.parquet/
│   │   ├── timeseries.parquet/
│   │   └── errors.parquet/
│   ├── Segment_002/                      # Segment 002 results
│   │   ├── 1/
│   │   ├── 2/
│   │   └── ...
│   └── ...
├── batch_segment.py                      # Segmentation generation script
└── README.md                             # This file
```

## Quick Start

### Option 1: Run All Segments (Recommended)

1. Open VS Code Command Palette: `Ctrl+Shift+P`
2. Type: `Run Task`
3. Select: **🚀 Segmentation Queue (Sequential)**

This runs all segments sequentially (Segment_001 → Segment_002 → ...).

### Option 2: Run Individual Segment

1. Open VS Code Command Palette: `Ctrl+Shift+P`
2. Type: `Run Task`
3. Select: **Calcul Segment XXX** (replace XXX with segment number)

## Configuration

### Base Configuration (`project.yaml`)

Contains common parameters for all segments:
- Simulation settings (timestep, year, run period, weather type)
- Output options (annual, timeseries, KPI settings)
- Upgrade settings (null by default)
- Parallel job count (N_JOBS = 20)

### Segment-Specific Configuration (auto-generated in `config/`)

Each `config/project_Segment_xxx.yaml` file:
- Inherits all parameters from `project.yaml`
- Overrides `SAMPLE_FILE` to point to the segment CSV
- Overrides `RESULTS_PATH` to point to segment-specific results directory
- Example:
  ```yaml
  SAMPLE_FILE : "../segments/segment_Segment_001.csv"
  HPXML_SCHEMA_FILE : "../../measures/BuildResidentialHPXML/measure.xml"
  RESULTS_PATH : "../results/Segment_001"
  ```

## Adding New Segments

When you add a new segment CSV file to `segments/`:

1. **Auto-generate configs** (recommended):
   ```bash
   uv run generate_segment_tasks.py
   ```
   This:
   - Creates `config/project_Segment_xxx.yaml` for each CSV
   - Updates `.vscode/tasks.json` with all segments
   - Adds new tasks to the sequential queue

2. **Manual approach** (if preferred):
   - Copy `project.yaml` to `config/project_Segment_xxx.yaml`
   - Update paths:
     - `SAMPLE_FILE` → `"../segments/segment_Segment_xxx.csv"`
     - `HPXML_SCHEMA_FILE` → `"../../measures/BuildResidentialHPXML/measure.xml"`
   - Add corresponding task to `.vscode/tasks.json`

## Task Queue Behavior

The sequential queue (`🚀 Segmentation Queue`) uses VS Code's `dependsOrder: "sequence"` to ensure:
- Tasks run one at a time
- Task B waits for Task A to complete before starting
- Output is combined in the terminal
- All segments are processed without parallelism

## Results Organization

Each segment's results are stored in its own subdirectory under `results/`:

```
Segmentation/results/Segment_001/
├── 1/                          # Building 1
├── 2/                          # Building 2
├── ...
├── results_job0.json.gz        # Summary JSON
├── metadata.parquet/           # Metadata dataset
├── timeseries.parquet/         # Timeseries dataset (if enabled)
└── errors.parquet/             # Errors dataset

Segmentation/results/Segment_002/
├── 1/
├── 2/
└── ...
```

Each segment runs independently and maintains its own complete set of simulation results. This makes it easy to:
- Run segments in parallel (if desired)
- Archive or backup individual segment results by directory
- Compare results across segments
- Re-run a single segment without affecting others

## Troubleshooting

### Task not showing in list
- Run: `uv run generate_segment_tasks.py` to regenerate tasks
- Reload VS Code window (Ctrl+R)

### OpenStudio not found
- Set `OPENSTUDIO_EXE` environment variable pointing to your OpenStudio installation
- Example (PowerShell):
  ```powershell
  $env:OPENSTUDIO_EXE = "C:\path\to\OpenStudio-3.9.0\bin\openstudio.exe"
  ```

### Schema validation error
- Verify `SCHEMA_VERSION` in project.yaml matches a file in `../../schemas/`
- Check that relative paths are correct (especially `HPXML_SCHEMA_FILE`)

### Weather file missing
- Verify `WEATHER_FILE_TYPE`, `SIMULATION_YEAR`, and region names in CSV match available weather files in `../../weather/`

## Command Reference

### Run all segments sequentially
```
Command Palette → Run Task → 🚀 Segmentation Queue (Sequential)
```

### Run specific segment
```
Command Palette → Run Task → Calcul Segment XXX
```

### Regenerate all configs and tasks
```bash
uv run generate_segment_tasks.py
```

### Manual run with specific config
```bash
cd Segmentation
uv run ../local.py config/project_Segment_001.yaml
```

## Notes

- Each segment runs independently with its own set of buildings
- Results are accumulated in `results/` directory
- BATCH_MODE is enabled for automatic cleanup after each building
- N_JOBS controls parallel building processing within each segment (not between segments)
