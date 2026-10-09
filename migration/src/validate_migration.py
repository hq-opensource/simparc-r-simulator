"""Validate a migration batch against the HPXML schemas."""

import argparse
import logging
import os
import random
import sys
from pathlib import Path

import pandas as pd

project_path = Path(__file__).resolve().parent.parent.parent
if project_path not in sys.path:
    sys.path.append(str(project_path))

from base import BuildStockBatchBase
from utils import get_project_configuration, path_rel_to_file
from hpxml_input_schema import extract_arguments_from_xml


logger = logging.getLogger(__name__)

def configure_logging(config_filepath: str):
    project_dir = Path(config_filepath).resolve().parent
    log_file = project_dir / "validation.log"

    if log_file.exists():
        log_file.unlink()

    formatter = logging.Formatter(
        "%(message)s"
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    logger.info("Logging initialized. Log file: %s", log_file)

class LocalBatch(BuildStockBatchBase):
    def __init__(self,project_filename):
        super().__init__(project_filename)
        
        # Determine n_jobs from config or use default
        if self.cfg.get("N_JOBS") is not None:
            n_jobs = self.cfg["N_JOBS"]
        else:
            n_jobs = int(os.cpu_count() - 8)

        if self.cfg["BATCH_MODE"]:
            logging.getLogger("preprocessing").setLevel(logging.ERROR)
        
        if sys.platform == "linux" or sys.platform == "linux2":
            self._parallel = {'backend': 'loky', 'n_jobs': n_jobs, 'verbose': 10,
                      'inner_max_num_threads': 2}
        else:
            self._parallel = {'backend': 'threading', 'n_jobs': n_jobs, 'verbose': 10}

    def run(self):
        # Get the building properties from a CSV file
        data = pd.read_csv(path_rel_to_file(self.cfg["CURRENT_PATH"], self.cfg["SAMPLE_FILE"]))

        # Define a seed for each building for reproducibility
        if "SEED" not in self.cfg:
            seed = random.randint(0, 2**31 - 1)
            self.cfg["SEED"] = seed
        else:
            seed = self.cfg["SEED"]

        data["seed"] = seed + data.index + 1

        

        # update cfg with old args
        old_config_path = Path("migration/version/measure_v110.xml")    
        self.cfg["OLD_ARGS_CONSTRAINTS"] = extract_arguments_from_xml(old_config_path) if old_config_path.exists() else {}

        data, list_columns_hpxml = preprocess_data_types(
            data,
            self.cfg["ARGS_CONSTRAINTS"],
            self.cfg.get("OLD_ARGS_CONSTRAINTS", {}),
        )

        logger.info("Validated %s rows across %s HPXML columns.", len(data), len(list_columns_hpxml))


def preprocess_data_types(data: pd.DataFrame, args_constraints: dict, old_args: dict):
    """
    Preprocess the input data based on the provided argument constraints
    so that each column gets the right data type.
    """
    dict_data_types = {
        'Boolean': bool,
        'Integer': int,
        'Choice': str,
        'Double': float,
        'String': str,
    }
    list_columns_hpxml = []
    old_args_keys = set(old_args.keys())
    # sort in alphabetical order for consistent processing
    old_args_keys = sorted(old_args_keys)

    for column in data.columns:
        if column in args_constraints:
            col_type = args_constraints[column]['Type']
            if col_type == 'String' or col_type == 'Choice':
                # Preserve NaN for string-like columns instead of converting to literal "nan"
                data[column] = data[column].where(data[column].isna(), data[column].astype(str))
            else:
                data[column] = data[column].astype(dict_data_types[col_type])
            list_columns_hpxml.append(column)
        elif column in old_args_keys:
            logger.warning("Column '%s' was in old constraint and is not mapped to a new valur. To investigate", column)

    return data, list_columns_hpxml


def main():
    parser = argparse.ArgumentParser(description="Batch launcher for SimParc")
    parser.add_argument("config_filepath", help="Path to the configuration file. (.yaml)")
    args = parser.parse_args()

    configure_logging(args.config_filepath)

    # Load the config once so the validator has access to the parsed schema paths.
    get_project_configuration(args.config_filepath)

    batch = LocalBatch(args.config_filepath)
    batch.run()


if __name__ == "__main__":
    main()

