# -*- coding: utf-8 -*-

import uuid,os,shutil,re,zipfile
import pandas as pd
import pyarrow as pa
from utils import get_project_configuration, read_csv
from postprocessing import write_dataframe_as_parquet
from pathlib import Path

class BuildStockBatchBase(object):
    LOGO = "   _____ _           ____                       ____        __       __  \n" \
           "  / ___/(_)___ ___  / __ \____ ___________     / __ )____ _/ /______/ /_ \n" \
           "  \__ \/ / __ `__ \/ /_/ / __ `/ ___/ ___/    / __  / __ `/ __/ ___/ __ \ \n" \
           " ___/ / / / / / / / ____/ /_/ / /  / /__     / /_/ / /_/ / /_/ /__/ / / /\n" \
           "/____/_/_/ /_/ /_/_/    \__,_/_/   \___/    /_____/\__,_/\__/\___/_/ /_/ \n"

    def __init__(self,project_file):
        self._uid = uuid.uuid4()
        self.cfg = get_project_configuration(project_file)

    @staticmethod
    def make_sim_dir(building_dir,overwrite_existing=True):
        sim_dir = str(building_dir)
        # Check to see if the simulation is done already and skip it if so.
        if os.path.exists(str(sim_dir)) and not overwrite_existing:
                raise FileExistsError("{} exists".format(str(sim_dir)))
        elif os.path.exists(str(sim_dir)) and not overwrite_existing:
            shutil.rmtree(sim_dir)

        # Create the simulation directory
        os.makedirs(sim_dir, exist_ok=overwrite_existing)
        return

    @staticmethod
    def cleanup_sim_dir(sim_dir):
        # Remove files already in data_point.zip
        zipfilename = os.path.join(sim_dir, "run", "data_point.zip")
        if os.path.isfile(zipfilename):
            with zipfile.ZipFile(zipfilename, "r") as zf:
                for filename in zf.namelist():
                    for filepath in (
                            os.path.join(sim_dir, "run", filename),
                            os.path.join(sim_dir, filename),
                    ):
                        if os.path.exists(filepath):
                            os.remove(filepath)
        # Copy to parent dir
        if os.path.exists(os.path.join(sim_dir, "run")):
            src_files = os.listdir(os.path.join(sim_dir, "run"))
            for file_name in src_files:
                full_file_name = os.path.join(os.path.join(sim_dir, "run"), file_name)
                if os.path.isfile(full_file_name):
                    shutil.copy(full_file_name, os.path.join(sim_dir,file_name))
            # remove run dir
            shutil.rmtree(os.path.join(sim_dir, "run"), ignore_errors=True)
        # Remove reports dir
        reports_dir = os.path.join(sim_dir, "reports")
        if os.path.isdir(reports_dir):
            shutil.rmtree(reports_dir, ignore_errors=True)
        # Remove generated_files dir
        generated_files_dir = os.path.join(sim_dir, "generated_files")
        if os.path.isdir(generated_files_dir):
            shutil.rmtree(generated_files_dir, ignore_errors=True)
        # Only keep .json and .zip
        # TODO remove csv and osw after seed in stochastic generation
        files = list(Path(sim_dir).iterdir())
        for f in files:
            if f.suffix != ".json" and f.suffix != ".zip" and f.suffix != ".log":
                Path.unlink(f)
        return