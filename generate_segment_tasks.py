#!/usr/bin/env python3
"""
Helper script to generate segment-specific project.yaml files and tasks.json
for the simparc-r-simulator segmentation workflow.

Usage:
    python generate_segment_tasks.py
"""

import json
import os
from pathlib import Path
import yaml

WORKSPACE_ROOT = Path(__file__).parent.resolve()
SEGMENTATION_DIR = WORKSPACE_ROOT / "Segmentation"
SEGMENTS_DIR = SEGMENTATION_DIR / "segments"
CONFIG_DIR = SEGMENTATION_DIR / "config"
VSCODE_DIR = WORKSPACE_ROOT / ".vscode"
BASE_PROJECT_FILE = SEGMENTATION_DIR / "project.yaml"


def get_segment_files():
    """Get all segment CSV files from segments directory."""
    if not SEGMENTS_DIR.exists():
        print(f"Segments directory not found: {SEGMENTS_DIR}")
        print(f"Current working directory: {os.getcwd()}")
        print(f"WORKSPACE_ROOT: {WORKSPACE_ROOT}")
        return []
    
    segment_files = sorted(SEGMENTS_DIR.glob("segment_*.csv"))
    print(f"Segments directory exists: {SEGMENTS_DIR}")
    print(f"Found {len(segment_files)} files")
    return segment_files


def extract_segment_name(csv_path):
    """Extract segment name from CSV filename."""
    # e.g., segment_Segment_001.csv -> Segment_001
    stem = csv_path.stem
    if stem.startswith("segment_"):
        return stem[8:]  # Remove "segment_" prefix
    return stem


def create_segment_project_yaml(segment_name, segment_csv_path):
    """Create a segment-specific project.yaml file."""
    # Read base project.yaml
    if not BASE_PROJECT_FILE.exists():
        print(f"Base project file not found: {BASE_PROJECT_FILE}")
        return False
    
    with open(BASE_PROJECT_FILE, 'r') as f:
        project_config = yaml.safe_load(f)
    
    # Update SAMPLE_FILE to point to the segment CSV (from config/ directory, need to go up)
    relative_csv_path = os.path.relpath(segment_csv_path, CONFIG_DIR)
    project_config['SAMPLE_FILE'] = relative_csv_path
    
    # Update HPXML_SCHEMA_FILE path (from config/ directory, need to go up to workspace)
    project_config['HPXML_SCHEMA_FILE'] = "../../measures/BuildResidentialHPXML/measure.xml"
    
    # Set RESULTS_PATH for segment (relative to config directory)
    project_config['RESULTS_PATH'] = f"../results/{segment_name}"
    
    # Write segment-specific project file to config directory
    output_file = CONFIG_DIR / f"project_{segment_name}.yaml"
    with open(output_file, 'w') as f:
        yaml.dump(project_config, f, default_flow_style=False, sort_keys=False)
    
    print(f"Created: {output_file}")
    return True


import json
from pathlib import Path

VSCODE_DIR = Path(".vscode")

def generate_tasks_json(segment_names):
    """Generate tasks.json with all segment tasks using 'process' type."""
    
    VSCODE_DIR.mkdir(exist_ok=True)
    
    base_tasks = [
        {
            "label": "Run local.py with project.yaml",
            "type": "process",
            "command": "${workspaceFolder}/.venv/bin/python",
            "args": [
                "-u",
                "local.py",
                "project.yaml"
            ],
            "options": {
                "cwd": "${workspaceFolder}"
            },
            "group": {
                "kind": "build",
                "isDefault": True
            },
            "presentation": {
                "reveal": "always",
                "panel": "shared",
                "clear": True
            },
            "problemMatcher": []
        }
    ]
    
    # Generate segment YAML files task
    generate_yamls_task = {
        "label": "Generate Segment YAML Files",
        "type": "process",
        "command": "${workspaceFolder}/.venv/bin/python",
        "args": [
            "-u",
            "${workspaceFolder}/generate_segment_tasks.py"
        ],
        "options": {
            "cwd": "${workspaceFolder}",
            "env": {
                "PYTHONUNBUFFERED": "1"
            }
        },
        "group": {
            "kind": "build"
        },
        "presentation": {
            "reveal": "always",
            "panel": "shared",
            "clear": True
        },
        "problemMatcher": []
    }
    base_tasks.append(generate_yamls_task)
    
    # Master queue task
    queue_task = {
        "label": "Segmentation Queue (Sequential)",
        "dependsOrder": "sequence",
        "dependsOn": ["Generate Segment YAML Files"] + [f"Calcul {name}" for name in segment_names],
        "group": {
            "kind": "build"
        },
        "presentation": {
            "reveal": "always",
            "panel": "shared",
            "echo": True
        },
        "problemMatcher": []
    }
    base_tasks.append(queue_task)
    
    # Individual segment tasks (Now using 'process')
    for segment_name in segment_names:
        task = {
            "label": f"Calcul {segment_name}",
            "type": "process",  # Changé en process ici aussi !
            "command": "${workspaceFolder}/.venv/bin/python",
            "args": [
                "-u",
                "${workspaceFolder}/local.py",
                f"${{workspaceFolder}}/Segmentation/config/project_{segment_name}.yaml"
            ],
            "options": {
                "cwd": "${workspaceFolder}",  # Exécuté à la racine pour éviter le crash de dossier manquant
                "env": {
                    "PYTHONUNBUFFERED": "1"
                }
            },
            "presentation": {
                "group": "segmentation_queue",
                "reveal": "always",
                "panel": "shared",
                "clear": False
            },
            "problemMatcher": []
        }
        base_tasks.append(task)
    
    tasks_config = {
        "version": "2.0.0",
        "tasks": base_tasks
    }
    
    output_file = VSCODE_DIR / "tasks.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(tasks_config, f, indent=2, ensure_ascii=False)
    
    print(f"Created: {output_file}")
    return True



def main():
    """Main function to generate all segment files and tasks."""
    print("Generating segment configurations...")
    print(f"Workspace root: {WORKSPACE_ROOT}")
    print(f"Segmentation directory: {SEGMENTATION_DIR}")
    print(f"Config directory: {CONFIG_DIR}")
    print()
    
    # Create config directory if it doesn't exist
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    # Create results directory if it doesn't exist
    results_dir = SEGMENTATION_DIR / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    
    # Get all segment CSV files
    segment_files = get_segment_files()
    if not segment_files:
        print("No segment files found. Please create segment CSV files in Segmentation/segments/")
        return
    
    print(f"Found {len(segment_files)} segment(s):")
    segment_names = []
    
    # Create project YAML for each segment
    for csv_path in segment_files:
        segment_name = extract_segment_name(csv_path)
        segment_names.append(segment_name)
        print(f"  - {segment_name}")
        create_segment_project_yaml(segment_name, csv_path)
        
        # Create segment results directory
        segment_results_dir = results_dir / segment_name
        segment_results_dir.mkdir(parents=True, exist_ok=True)
        print(f"    Created directory: {segment_results_dir}")
    
    print()
    
    # Generate tasks.json
    print("Generating tasks.json...")
    generate_tasks_json(segment_names)
    
    print()
    print("✅ Done! You can now run the segmentation queue from VS Code:")
    print("   Run task: '🚀 Segmentation Queue (Sequential)'")
    print()
    print("Results will be stored in segment-specific directories:")
    for segment_name in segment_names:
        print(f"  - Segmentation/results/{segment_name}/")


if __name__ == "__main__":
    main()
