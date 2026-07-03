# -*- coding: utf-8 -*-

import logging,yaml,os
import pandas as pd
from pathlib import Path
from hpxml_input_schema import extract_arguments_from_xml

logger = logging.getLogger(__name__)

def read_csv(csv_file_path, **kwargs) -> pd.DataFrame:
    default_na_values = pd._libs.parsers.STR_NA_VALUES
    df = pd.read_csv(
        csv_file_path,
        na_values=list(default_na_values - {"None", "NA"}),
        keep_default_na=False,
        **kwargs,
    )
    return df

def path_rel_to_file(project_dir, x):
    base_path = Path(project_dir)
    if Path(x).is_absolute():
        return Path(x).absolute()
    else:
        return (base_path/Path(x)).resolve()

def get_project_configuration(project_file):
    try:
        with open(project_file) as f:
            cfg = yaml.load(f, Loader=yaml.SafeLoader)
    except FileNotFoundError as err:
        logger.error("Failed to load input yaml for validation")
        raise err

    cfg["ARGS_CONSTRAINTS"]=extract_arguments_from_xml(Path(project_file).parent.absolute() / cfg["HPXML_SCHEMA_FILE"])

    # Set absolute paths
    cfg["CURRENT_PATH"] = Path(project_file).parent.absolute()
    cfg["CONFIG_PATH"] = Path(project_file).absolute()
    cfg["RESULTS_PATH"] = cfg["CURRENT_PATH"] / "results"
    cfg["MEASURES_PATH"] = cfg["CURRENT_PATH"] / "measures"
    cfg["WEATHER_FILES_PATH"] = cfg["CURRENT_PATH"] / "weather"

    return cfg