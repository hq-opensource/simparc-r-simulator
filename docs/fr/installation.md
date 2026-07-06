# Installation

Vous pouvez executer SimParc-R de deux facons principales.

## Option A: UV + SDK OpenStudio local

1. Installer UV: <https://docs.astral.sh/uv/getting-started/installation/>
2. Installer OpenStudio SDK 3.9.0: <https://github.com/NREL/OpenStudio/releases/tag/v3.9.0>
3. Installer les dependances du projet:

```bash
uv sync
```

4. Definir `OPENSTUDIO_EXE` avec le chemin de l'executable OpenStudio, ou ajouter le dossier `bin` de OpenStudio au `PATH`.

Exemple PowerShell:

```powershell
$env:OPENSTUDIO_EXE = "C:\path\to\OpenStudio-3.9.0\bin\openstudio.exe"
```

## Option B: Dev Container

1. Installer Docker.
2. Installer VS Code et l'extension Dev Containers.
3. Ouvrir le depot dans son conteneur de developpement.
