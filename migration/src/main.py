import argparse

from migration.src.migrate_csv import main as migrate_main
from migration.src.validate_csv import main as validate_main


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
