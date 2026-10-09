"""Convenience wrapper to run the migration tool on a CSV file."""

import sys
from pathlib import Path

from migration.src.migrate_csv import main as migrate_main


def main():
    repo_root = Path(__file__).resolve().parent
    default_csv = repo_root / "test-building-stock-csv" / "building-stock-example.csv"

    csv_path = sys.argv[1] if len(sys.argv) > 1 else str(default_csv)
    migrate_main(csv_path)

if __name__ == "__main__":
    main()