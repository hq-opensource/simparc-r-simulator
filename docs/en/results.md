# Results and Outputs

Simulation outputs are written under `results/`.

## Main output artifacts

- Per-building folders (logs and workflow outputs).
- `results_job0.json.gz`: compact summary of simulation outputs.
- `metadata.parquet/`: partitioned metadata dataset.
- `timeseries.parquet/`: partitioned time-series dataset (if enabled).
- `errors.parquet/`: partitioned failures dataset.

## Typical analysis path

1. Inspect `errors.parquet/` first to identify failed cases.
2. Review `metadata.parquet/` for annual metrics and building-level context.
3. Use `timeseries.parquet/` for temporal analysis and peak/load studies.

## Notes

Large simulation batches can generate significant output volume. Plan storage and retention accordingly.
