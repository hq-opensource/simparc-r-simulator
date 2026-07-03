# Import necessary libraries
import pandas as pd
import json
import os
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path
from pyarrow import parquet
from postprocess.Analyse import Quantite_interet, Quantite_interet_description

def read_out_osw(fs, filename):
    try:
        with fs.open(filename, "r") as f:
            d = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    else:
        out_d = {}
        keys_to_copy = ["started_at", "completed_at", "completed_status"]
        for key in keys_to_copy:
            out_d[key] = d.get(key, None)
        for step in d.get("steps", []):
            if step["measure_dir_name"] == "BuildExistingModel":
                out_d["building_id"] = step["arguments"]["building_id"]
        return out_d

def read_data_point_out_json(fs,filename):
    try:
        with fs.open(filename, "r") as f:
            d = json.load(f)
        if not d:
            return None
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    else:
        sim_out_report = "SimulationOutputReport"
        if "ReportSimulationOutput" in d:
            sim_out_report = "ReportSimulationOutput"

        if sim_out_report not in d:
            d[sim_out_report] = {"applicable": False}
        return d


def flatten_datapoint_json(d):
    new_d = {}
    cols_to_keep = {"ApplyUpgrade": ["upgrade_name", "applicable"]}
    for k1, k2s in cols_to_keep.items():
        for k2 in k2s:
            new_d[f"{k1}.{k2}"] = d.get(k1, {}).get(k2)

    # copy over all the key and values from BuildExistingModel
    col1 = "BuildExistingModel"
    for k, v in d.get(col1, {}).items():
        new_d[f"{col1}.{k}"] = v

    # if there is no units_represented key, default to 1
    # TODO @nmerket @rajeee is there a way to not apply this to Commercial jobs? It doesn't hurt, but it is weird for us
    units = int(new_d.get(f"{col1}.units_represented", 1))
    new_d[f"{col1}.units_represented"] = units
    sim_out_report = "SimulationOutputReport"
    if "ReportSimulationOutput" in d:
        sim_out_report = "ReportSimulationOutput"
    col2 = sim_out_report
    for k, v in d.get(col2, {}).items():
        new_d[f"{col2}.{k}"] = v
    return new_d

def read_simulation_outputs(fs, sim_dir):
    dpout = read_data_point_out_json(fs, f"{sim_dir}/run/data_point_out.json")
    if dpout is None:
        dpout = {}
    else:
        dpout = flatten_datapoint_json(dpout)
    out_osw = read_out_osw(fs, f"{sim_dir}/out.osw")
    if out_osw:
        dpout.update(out_osw)
    return dpout

def write_dataframe_as_parquet(df, fs, filename, schema=None):
    tbl = pa.Table.from_pandas(df, schema=schema, preserve_index=False)
    with fs.open(filename, "wb") as f:
        parquet.write_table(tbl, f)

# Define the postprocessing function
def postprocess_results(path):
    """
    This function is used to post-process the results of the simulation
    For now, it processes simulation status and error messages for each building.
    Inputs:
    - i: dictionary containing the building properties (from the input CSV)
    Outputs:
    - None (results are saved as parquet files in the results directory)

    """
    try:
        with open(os.path.join(path, "{}_metadata.json".format(str(Path(path).stem))), "r") as f:
            metadata_json =json.load(f)
            i = metadata_json["hpxml_args"] | metadata_json["non_hpxml_args"]
    except FileNotFoundError as e:
        i = {}
        i['status'] = "Fail"
        i['failure_message'] = "{}_metadata.json : File not found.".format(str(Path(path).stem))
        return

    i["building_id"] = str(Path(path).stem)
    # Read the out.osw file
    out_osw_path = os.path.join(path, 'out.osw')
    try:
        with open(out_osw_path, 'r') as f:
            out_osw = json.load(f)
    except FileNotFoundError as e:
        i['status'] = "Fail"
        i['failure_message'] = "{}/out.osw : File not found.".format(str(Path(path)))
        return

    # Get the status of the simulation
    i['status'] = out_osw.get('completed_status', None)
    # Get the failed step if any
    i['last_step'] = out_osw['steps'][out_osw['current_step']-1].get('measure_dir_name', None)
    i['failure_message'] = out_osw['steps'][out_osw['current_step']-1]['result'].get('step_errors', None)
    if i['status'] == 'Success':
        # Collect all columns names
        columns_to_be_str = list(i.keys())
        # Add the annual results
        results_annual_path = os.path.join(path, 'run', 'results_annual.csv')
        df_annual_results = pd.read_csv(results_annual_path,header=None)
        dict_annual_results = df_annual_results.set_index(0).T.to_dict('records')[0]
        i.update(dict_annual_results)
        # Add the timeseries results
        if (Path(path) / 'run' / 'results_timeseries.csv').exists():
            dfTimeseries = pd.read_csv(os.path.join(path, 'run', 'results_timeseries.csv'),
                                    header=[0,1])
            dfTimeseries.columns = ['_'.join([str(i) for i in col if ((str(i) != 'nan') & (str(i)[:8] != "Unnamed:"))]) \
                                    for col in dfTimeseries.columns.values]
            
            # Calculate quantities of interest from timeseries data
            try:
                dict_quantites_interet = Quantite_interet(dfTimeseries)
                i.update(dict_quantites_interet)
            except Exception as e:
                print(f"Warning: Failed to calculate quantities of interest for building {i['building_id']}: {e}")
            
            dfTimeseries['building_id'] = i['building_id']
            tableTimeseries = pa.Table.from_pandas(dfTimeseries)
            pq.write_to_dataset(tableTimeseries,
                                root_path=os.path.join(str(Path(path).parent), 'timeseries.parquet'),
                                partition_cols=['building_id'],
                                existing_data_behavior='delete_matching')
        # Convert the dictionary to a pandas DataFrame and save it as a parquet file
        dfMetadata = pd.DataFrame([i])
        dfMetadata[columns_to_be_str] = dfMetadata[columns_to_be_str].astype(str)
        tableMetadata = pa.Table.from_pandas(dfMetadata)
        pq.write_to_dataset(tableMetadata,
                            root_path=os.path.join(str(Path(path).parent), 'metadata.parquet'),
                            partition_cols=['building_id'],
                            existing_data_behavior='delete_matching')
    else:
        # If the simulation failed, just save the dict i into a json file
        dfErrors = pd.DataFrame([i])
        tableErrors = pa.Table.from_pandas(dfErrors)
        pq.write_to_dataset(tableErrors,
                            root_path=os.path.join(str(Path(path).parent), 'errors.parquet'),
                            partition_cols=['building_id'],
                            existing_data_behavior='delete_matching')

    return

if "__main__" == __name__:
    postprocess_results("/home/gilbert/SimParc/LTE-OpenStudioCLI-Test/results/182")