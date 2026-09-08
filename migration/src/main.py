import argparse
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from migrate_csv import main as migrate_main


def build_parser():
    parser = argparse.ArgumentParser(
        description="Migrate CSV files from HPXML v1.10 to v1.12 format."
    )
    parser.add_argument(
        "input", metavar="INPUT_FILE", help="Path to the input CSV file"
    )
    parser.add_argument(
        "output",
        metavar="OUTPUT_FILE",
        nargs="?",
        default=None,
        help="Optional path to the output CSV file",
    )
    return parser


def main():
    args = build_parser().parse_args()
    migrate_main(args.input, args.output)


if __name__ == "__main__":
    main()
