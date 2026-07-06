# Running Simulations

## Run a full batch

```bash
uv run local.py project.yaml
```

## What happens during a run

1. The YAML config is loaded and validated.
2. Input data is preprocessed and transformed.
3. Upgrade scenarios are applied when configured.
4. Each building gets its simulation directory and OSW file.
5. OpenStudio runs are executed in parallel.
6. Outputs are collected and post-processed.

## Troubleshooting basics

- If OpenStudio is not found, verify `OPENSTUDIO_EXE` or `PATH`.
- If schema validation fails, verify `SCHEMA_VERSION` and required fields.
- If weather mapping fails, verify region names and weather settings in input/config.
