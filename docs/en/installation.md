# Installation

You can run SimParc-R in two common ways.

## Option A: UV + local OpenStudio SDK

1. Install UV: <https://docs.astral.sh/uv/getting-started/installation/>
2. Install OpenStudio SDK 3.9.0: <https://github.com/NREL/OpenStudio/releases/tag/v3.9.0>
3. Install project dependencies:

```bash
uv sync
```

4. Set `OPENSTUDIO_EXE` to your OpenStudio executable path, or add OpenStudio `bin` to your `PATH`.

PowerShell example:

```powershell
$env:OPENSTUDIO_EXE = "C:\path\to\OpenStudio-3.9.0\bin\openstudio.exe"
```

## Option B: Dev Container

1. Install Docker.
2. Install VS Code + Dev Containers extension.
3. Reopen the repository in its development container.
