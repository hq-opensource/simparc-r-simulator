# -*- coding: utf-8 -*-

import uuid,os,shutil,re,zipfile,time
import pandas as pd
import pyarrow as pa
from utils import get_project_configuration, read_csv
from postprocessing import write_dataframe_as_parquet
from pathlib import Path
from urllib.parse import quote, unquote

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
        elif os.path.exists(str(sim_dir)) and overwrite_existing:
            shutil.rmtree(sim_dir)

        # Create the simulation directory
        os.makedirs(sim_dir, exist_ok=overwrite_existing)
        return

    @staticmethod
    def remove_building_results(results_dir, building_id):
        # Remove the building partition from every parquet dataset (errors, metadata, timeseries, ...)
        for dataset in Path(results_dir).glob("*.parquet"):
            if dataset.is_dir():
                for name in {f"building_id={building_id}", f"building_id={quote(str(building_id), safe='')}"}:
                    shutil.rmtree(dataset / name, ignore_errors=True)

    STATUS_LOG = "batch_status.log"

    @staticmethod
    def log_status(results_dir, building_id, state, message=""):
        # Append one line 'timestamp;building_id;state;message' to the single status log.
        # One small O_APPEND write per call: no shared handle, no lock, safe for threads/processes.
        msg = " ".join(str(message).replace(";", ",").split())[:500]
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')};{building_id};{state};{msg}\n".encode("utf-8")
        try:
            fd = os.open(os.path.join(results_dir, BuildStockBatchBase.STATUS_LOG),
                         os.O_WRONLY | os.O_APPEND | os.O_CREAT)
            try:
                os.write(fd, line)
            finally:
                os.close(fd)
        except OSError:
            pass  # e.g. disk full: the previous state stays in the log

    @staticmethod
    def current_status(results_dir):
        # Last state of each building: {building_id: (state, message)}
        path = os.path.join(results_dir, BuildStockBatchBase.STATUS_LOG)
        last = {}
        if os.path.isfile(path):
            with open(path, encoding="utf-8", errors="replace") as fh:
                for ln in fh:
                    p = ln.rstrip("\n").split(";", 3)
                    if len(p) == 4:
                        last[p[1]] = (p[2], p[3])  # last line wins
        return last

    @classmethod
    def reconcile_status(cls, results_dir, building_ids=None):
        # Buildings left 'queued' or 'running' did not finish (crash, disk full, kill): mark them failed
        ids = None if building_ids is None else {str(b) for b in building_ids}
        for bid, (state, _) in cls.current_status(results_dir).items():
            if state in ("queued", "running") and (ids is None or bid in ids):
                cls.log_status(results_dir, bid, "failed",
                               f"incomplete (was {state}: crash, disk full or killed)")

    @staticmethod
    def list_failed_and_missing_ids(results_dir, building_ids):
        # Failed = partition in errors.parquet or last state in batch_status.log not 'success';
        # missing = no results folder
        results_dir = Path(results_dir)
        errors_dir = results_dir / "errors.parquet"
        failed = set()
        if errors_dir.is_dir():
            failed = {unquote(d.name.split("=", 1)[1]) for d in errors_dir.glob("building_id=*")}
        failed |= {b for b, (state, _) in BuildStockBatchBase.current_status(str(results_dir)).items()
                   if state != "success"}
        return {str(b) for b in building_ids if str(b) in failed or not (results_dir / str(b)).is_dir()}

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