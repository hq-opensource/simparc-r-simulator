# -*- coding: utf-8 -*-
import pandas as pd
import argparse, yamale, gzip, json, sys
import time, subprocess
import os
from fsspec.implementations.local import LocalFileSystem
from datetime import timedelta
from joblib import Parallel, delayed, parallel_config
from building import Building
import functools, gc, shutil, re, tarfile, random

# Import local libraries
from preprocessing import preprocess_data_types, preprocess_data_to_dict	# function to preprocess the data
from upgrading import apply_upgrades	# function to apply upgrades to the building data
from postprocessing import postprocess_results, read_simulation_outputs	# function to post-process the results
from base import BuildStockBatchBase
from utils import *

logger = logging.getLogger(__name__)

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

    @classmethod
    def validate_project(cls, project_file):
        assert cls.validate_project_schema(project_file)
        logger.info("Base Validation Successful")
        return True

    @staticmethod
    def validate_project_schema(project_file):
        cfg = get_project_configuration(project_file)
        schema_version = cfg.get("SCHEMA_VERSION")
        version_schema = os.path.join(os.path.dirname(__file__), "schemas", f"v{schema_version}.yaml")
        if not os.path.isfile(version_schema):
            logger.error(f"Could not find validation schema for YAML version {schema_version}")
            raise FileNotFoundError(version_schema)
        schema = yamale.make_schema(version_schema)
        data = yamale.make_data(project_file, parser="ruamel")
        return yamale.validate(schema, data, strict=True)

    @classmethod
    def run_building(cls,cfg,building_data):
        # Wrapper: logs queued/running/success/failed in the single batch_status.log
        results_dir = os.path.join(cfg["CURRENT_PATH"], cfg["RESULTS_PATH"])
        bid = building_data['non_hpxml_args']['building_id']
        cls.log_status(results_dir, bid, "running")
        dpout, error = None, None
        try:
            free = shutil.disk_usage(results_dir).free
            min_free = cfg.get("MIN_FREE_DISK_GB", 5) * 1024**3
            if free < min_free:
                raise OSError(f"low disk space: {free / 1024**3:.1f} GB free")
            dpout, error = cls._run_building(cfg, building_data)
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
        cls.log_status(results_dir, bid, "failed" if error else "success", error or "simulation completed")
        return dpout

    @classmethod
    def _run_building(cls,cfg,building_data):
        error = None
        # Create a new folder named 'building_1' in results_dir
        building_dir = Path(os.path.join(cfg["CURRENT_PATH"], cfg["RESULTS_PATH"],
                                    str(building_data['non_hpxml_args']['building_id'])))

        cls.remove_building_results(building_dir.parent, building_dir.name)
        cls.make_sim_dir(building_dir)

        # Dump metadata to a JSON file
        # TODO improve this
        with open(os.path.join(building_dir, "{}_metadata.json".format(str(building_data['non_hpxml_args']['building_id']))), "w") as f:
            json.dump(building_data, f, indent=4)
        f.close()

        # Correct the paths in hpxml_args
        building_data['hpxml_args']['hpxml_path'] = str(building_dir / 'built.xml')
        
		# Define the right weather file path based on the weather file type, the simulation year and the administrative region
        with open('weather/mapping/Mapping-Region-EPWfiles.json', 'r') as f:
            mapping_region_weather = json.load(f)  
        building_data['hpxml_args']['weather_station_epw_filepath'] = os.path.join(cfg["CURRENT_PATH"],
                                                                                   cfg["WEATHER_FILES_PATH"],
                                                                                   mapping_region_weather[cfg["WEATHER_FILE_TYPE"]][str(cfg["SIMULATION_YEAR"])].get(building_data['non_hpxml_args']['Region_Administrative']))

        # Define the simulation settings
        building_data['hpxml_args']['simulation_control_timestep'] = cfg["SIMULATION_TIMESTEP"]
        building_data['hpxml_args']['simulation_control_run_period'] = cfg["SIMULATION_RUN_PERIOD"]

        # Define a new building based on the CSV data
        building_i = Building(building_data,cfg,)

        # Generate stochastic profiles for diverse appliances if needed
        building_i.generate_stochastic_profile(building_dir)

        # Create the OpenStudio Workflow (OSW) file for the building
        building_i.create_osw(cfg["CURRENT_PATH"], building_dir)

        # Run the OpenStudio workflow using the command line
        container_aware = os.environ.get('AM_I_IN_A_DOCKER_CONTAINER', False)
        start_time = time.perf_counter()
        with open(building_dir / "openstudio_output.log", "w") as f_out:
            subprocess_kw ={"check":True,"stdout":f_out,"stderr":subprocess.STDOUT}
            try:
                if container_aware:
                    subprocess.run(["openstudio", "run", "-w", building_dir / "in.osw"],**subprocess_kw) # with devcontainer
                else:
                    openstudio_exe = os.environ.get("OPENSTUDIO_EXE", "").strip().strip('"')
                    if not openstudio_exe:
                        openstudio_exe = shutil.which("openstudio")
                    if not openstudio_exe:
                        raise EnvironmentError(
                            "OPENSTUDIO_EXE is not defined and 'openstudio' is not available in PATH. "
                            "Set OPENSTUDIO_EXE (absolute path to openstudio executable) or add OpenStudio bin to PATH."
                        )
                    subprocess.run([openstudio_exe, "run", "-w", building_dir / "in.osw"],**subprocess_kw) # with OpenStudio SDK configured as env var or PATH
            except subprocess.TimeoutExpired as e:
                print(str(building_dir))
                print(str(e))
                error = f"openstudio timeout: {e}"
            except subprocess.CalledProcessError as e:
                print(e)
                error = f"openstudio exit code {e.returncode}: {cls.tail_line(building_dir / 'openstudio_output.log')}"
            finally:
                if error is None and (building_dir / "run" / "failed.job").exists():
                    error = "openstudio failed.job: " + cls.tail_line(building_dir / "openstudio_output.log")
                fs = LocalFileSystem()
                dpout = read_simulation_outputs(fs,str(building_dir))
                if cfg["BATCH_MODE"]:
                    postprocess_results(building_dir, cfg)
                if cfg.get("CLEANUP", True):
                    cls.cleanup_sim_dir(building_dir)
                del cfg
                del building_data
                gc.collect()
        return dpout, error

    @staticmethod
    def tail_line(path, n=4000):
        # Last non-empty line of a (possibly large) log file, reading only its end
        try:
            with open(path, "rb") as f:
                f.seek(0, os.SEEK_END)
                f.seek(max(0, f.tell() - n))
                lines = f.read().decode("utf-8", "replace").strip().splitlines()
                return lines[-1] if lines else "empty openstudio log"
        except OSError:
            return "no openstudio log"

    def run_batch(self):
        start_time = time.perf_counter()

        # Get the building properties from a CSV file
        data = pd.read_csv(path_rel_to_file(self.cfg["CURRENT_PATH"], self.cfg["SAMPLE_FILE"]))
        
		# Define a seed for each building for reproducibility
        if "SEED" not in self.cfg:
            SEED = random.randint(0,2**31-1)
            self.cfg["SEED"] = SEED
        else:
            SEED = self.cfg["SEED"]
        
        if 'seed' not in data.columns:
            data['seed'] = SEED + data.index + 1
        else:
            #ajoute un seed si manquant
            fallback_seeds = pd.Series(SEED + data.index + 1, index=data.index)
            data['seed'] = data['seed'].fillna(fallback_seeds).astype(int)

        # Preprocess the data to ensure it meets the constraints
        data, list_columns_hpxml = preprocess_data_types(data, self.cfg["ARGS_CONSTRAINTS"])

        # Apply upgrades
        data_upgrades = apply_upgrades(self,data)  # Apply upgrades to the building data

        # Preprocess the data to get a dictionary
        dp_list = preprocess_data_to_dict(data, self.cfg["ARGS_CONSTRAINTS"], list_columns_hpxml)
        data_upgrades_dict = preprocess_data_to_dict(data_upgrades, self.cfg["ARGS_CONSTRAINTS"], list_columns_hpxml)
        
        # Create a new folder named 'results' in current_dir
        results_dir = os.path.join(self.cfg["CURRENT_PATH"], self.cfg["RESULTS_PATH"])
        if not os.path.exists(results_dir):
            os.makedirs(results_dir)

        # Buildings left queued/running by a previous crashed run are marked failed
        self.reconcile_status(results_dir)

        if data_upgrades_dict is not None:
            sim_list = dp_list + data_upgrades_dict
        elif data_upgrades_dict is None:
            sim_list = dp_list

        # Select the buildings to (re)compute
        recompute = self.cfg.get("RECOMPUTE_FAIL_MISSING", False)
        if recompute is True:
            ids = self.list_failed_and_missing_ids(results_dir, [s['non_hpxml_args']['building_id'] for s in sim_list])
            sim_list = [s for s in sim_list if str(s['non_hpxml_args']['building_id']) in ids]
        elif recompute:
            ids = {str(i) for i in recompute}
            sim_list = [s for s in sim_list if str(s['non_hpxml_args']['building_id']) in ids]

        all_sims = map(delayed(functools.partial(self.run_building,self.cfg)),sim_list)

        for s in sim_list:
            self.log_status(results_dir, s['non_hpxml_args']['building_id'], "queued")

        print("------------------------------------------------------\n")
        # Print the number of simulations to run
        print("Running {} simulations with {} workers...".format(len(sim_list),self._parallel["n_jobs"]))
        try:
            with parallel_config(**self._parallel):
                dpouts = Parallel()(all_sims)
        finally:
            # Anything still queued/running here did not finish (worker killed, batch aborted)
            self.reconcile_status(results_dir, [s['non_hpxml_args']['building_id'] for s in sim_list])
        dpouts = [d for d in dpouts if d is not None]

        sim_out_path = Path(self.cfg["RESULTS_PATH"])

        results_job_json_filename = sim_out_path / "results_job0.json.gz"
        with gzip.open(str(results_job_json_filename), "wt", encoding="utf-8") as f:
            json.dump(dpouts, f)
        del dpouts

        print("simulations completed.")
        duration = timedelta(seconds=time.perf_counter() - start_time)
        print("Batch duration : {}".format(duration))
        print("Batch processing complete.")

    def postprocess_sims(self):
        if self.cfg["BATCH_MODE"]:
            return

        start_time = time.perf_counter()

        postprocess_paths = [f.path for f in os.scandir(self.cfg["RESULTS_PATH"]) if f.is_dir()]
        postprocess_sims = map(delayed(functools.partial(postprocess_results, cfg=self.cfg)), postprocess_paths)

        # Print the number of building results to post-process
        print("Running post-processing for {} simulation results with {} workers...".format(len(postprocess_paths),self._parallel["n_jobs"]))
        # Parallel post-processing
        with parallel_config(**self._parallel):
            Parallel()(postprocess_sims)

        # # Print completion message
        duration = timedelta(seconds=time.perf_counter() - start_time)
        print("Postprocessing duration : {}".format(duration))
        print("Postprocessing completed.")
        print("------------------------------------------------------\n")
        return 0

def main():
    print(BuildStockBatchBase.LOGO)
    parser = argparse.ArgumentParser(description="Batch launcher for SimParc")
    parser.add_argument("config_filepath", help="Path to the configuration file. (.yaml)")
    parser.add_argument("--postprocessonly",help="Only do postprocessing, useful for when the simulations are already done",action="store_true")
    args = parser.parse_args()

    b = LocalBatch(args.config_filepath)

    if not args.postprocessonly and b.validate_project_schema(args.config_filepath):
        b.run_batch()

    b.postprocess_sims()

if __name__ == "__main__":
    main()
