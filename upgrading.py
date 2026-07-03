# Import necessary libraries
import pandas as pd
import operator

OPERATORS = {
    "==": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    "<": operator.lt,
    ">=": operator.ge,
    "<=": operator.le,
    "in": lambda series, values: _in_operator(series, values),
    "not in": lambda series, values: _not_in_operator(series, values),
}

def _in_operator(series: pd.Series, values) -> pd.Series:
    """Return True where each value of the series is contained in values."""
    if not isinstance(values, (list, tuple, set)):
        raise ValueError(
            "For operator 'in', the condition value must be a list, tuple, or set. "
            f"Received: {type(values).__name__}"
        )
    return series.isin(values)

def _not_in_operator(series: pd.Series, values) -> pd.Series:
    """Return True where each value of the series is not contained in values."""
    return ~_in_operator(series, values)

def evaluate_condition(df: pd.DataFrame, condition: list) -> pd.Series:
    """
    Evaluate a single condition on the DataFrame and return a boolean mask.
    Args:
        df (DataFrame): The DataFrame to evaluate.
        condition (list): A list containing the column name, operator, and value.

    Returns:
        Series: A boolean mask indicating which rows satisfy the condition.
    """
    if not isinstance(condition, list) or len(condition) != 3:
        raise ValueError(
            "A condition must be a list with 3 items: [column_name, operator, value]. "
            f"Received: {condition}"
        )

    col, op, val = condition
    if op not in OPERATORS:
        raise ValueError(f"Unsupported operator: {op}")
    if col not in df.columns:
        raise ValueError(f"Unknown column in filter condition: {col}")

    return OPERATORS[op](df[col], val)


def build_filter_mask(df: pd.DataFrame, filters) -> pd.Series:
    """
    Build a boolean mask for the DataFrame based on provided filters.

    Supported filter formats:
        - Atomic condition list:
            ["col1", "==", "value"]
        - Logical dictionary format (explicit syntax):
      {"all": [ ... ]}, {"any": [ ... ]}, {"not": ...}
    """
    if filters in (None, [], {}):
        return pd.Series(True, index=df.index)

    # A list now represents a single atomic condition only.
    if isinstance(filters, list):
                return evaluate_condition(df, filters)

    if isinstance(filters, dict):
        allowed_keys = {"all", "any", "not"}
        unknown_keys = set(filters.keys()) - allowed_keys
        if unknown_keys:
            raise ValueError(
                "Unsupported filter key(s): "
                f"{sorted(unknown_keys)}. Allowed keys are: {sorted(allowed_keys)}"
            )

        logical_keys = [key for key in ("all", "any", "not") if key in filters]
        if len(logical_keys) != 1:
            raise ValueError(
                "Each logical filter node must define exactly one key among "
                "['all', 'any', 'not']. "
                f"Received keys: {sorted(filters.keys())}"
            )

        if "all" in filters:
            mask = pd.Series(True, index=df.index)
            for item in filters["all"]:
                mask &= build_filter_mask(df, item)
            return mask

        if "any" in filters:
            mask = pd.Series(False, index=df.index)
            for item in filters["any"]:
                mask |= build_filter_mask(df, item)
            return mask

        if "not" in filters:
            mask = pd.Series(True, index=df.index)
            for item in filters["not"]:
                mask &= build_filter_mask(df, item)
            return ~mask

    raise ValueError(f"Unsupported filter structure: {filters}")


def apply_filters(df: pd.DataFrame, filters):
    """Apply the provided filters to the DataFrame and return the filtered DataFrame.
    Args:
        df (DataFrame): The DataFrame to filter.
        filters: The filter conditions to apply.
        Returns:
        DataFrame: The filtered DataFrame.
    """
    return df[build_filter_mask(df, filters)]

def wall_insulation(df: pd.DataFrame, improvement_rate: float):
    """
    Apply the new wall insulation value based on the improvement rate.

    Args:
        df (DataFrame): The DataFrame containing building data.
        improvement_rate (float): The percentage improvement rate (fraction).

    Returns:
        df (DataFrame): The DataFrame with updated wall insulation values.

    """
    df['wall_assembly_r'] = df['wall_assembly_r'] * (1 + improvement_rate)

    return df

def set_ceiling_insulation(df: pd.DataFrame, new_insulation_value: float):
    """
    Set the new ceiling insulation value.

    Args:
        df (DataFrame): The DataFrame containing building data.
        new_insulation_value (float): The new R-value for ceiling insulation.

    Returns:
        df (DataFrame): The DataFrame with updated ceiling insulation values.

    """
    df['ceiling_assembly_r'] = new_insulation_value

    return df

def set_wall_insulation_to_standard(df: pd.DataFrame, standard_name: str):
    """
    Set the new wall insulation value based on the standard name.

    Args:
        df (DataFrame): The DataFrame containing building data.
        standard_name (str): The name of the standard to set ("Building Code 2020 QC", 
        "Novoclimat 2024" or "PassivHaus").

    Returns:
        df (DataFrame): The DataFrame with updated wall insulation values.

    """
    # Define standard values for wall insulation based on the standard name
    standard_values = {
        "Building Code 2020 QC": {
            "< 6000 DJC": 3.6*5.678,  # RSI-value to R-value (effective R-value) - < 6000 heating degree days (18degC base)
            ">= 6000 DJC": 4.05*5.678   # RSI-value to R-value (effective R-value) - >= 6000 heating degree days (18degC base)
        },
        "Novoclimat 2024": {
            "Maison et petit multilogement": {
                 "< 6000 DJC": 4.14*5.678,  # RSI-value to R-value (effective R-value) - < 6000 heating degree days (18degC base)
                 ">= 6000 DJC": 4.4*5.678   # RSI-value to R-value (effective R-value) - >= 6000 heating degree days (18degC base)
            },
            "Grand multilogement": 3.6*5.678  # RSI-value to R-value (effective R-value)
        },
        "PassivHaus": {
            "< 6000 DJC": 40,	# RSI-value of around 7.0
            ">= 6000 DJC": 45	# RSI-value of around 7.9
        }
    }
    # Administrative regions list (first assumptions) - Variable "Region_Administrative"
    regions_6000DJCplus = ["Bas-Saint-Laurent", "Côte-Nord", "Gaspésie-Îles-de-la-Madeleine", "Saguenay-Lac-Saint-Jean"]
    regions_6000DJCplus_mask = df['Region_Administrative'].isin(regions_6000DJCplus)
    regions_6000DJCmoins_mask = ~regions_6000DJCplus_mask
    
    # Variable "Type_Logement" - Only the value "Collective" is considered for the "Grand multilogement" category, all other values are considered for the "Maison et petit multilogement" category
    grand_multilogement_mask = df['Type_Logement'] == "Collective"
    maison_petit_multilogement_mask = ~grand_multilogement_mask
    
    # Apply the standard values based on the standard name and the conditions for the different categories
    if standard_name == "Novoclimat 2024":
        df.loc[regions_6000DJCplus_mask & maison_petit_multilogement_mask, 'wall_assembly_r'] = standard_values[standard_name]["Maison et petit multilogement"][">= 6000 DJC"]
        df.loc[regions_6000DJCmoins_mask & maison_petit_multilogement_mask, 'wall_assembly_r'] = standard_values[standard_name]["Maison et petit multilogement"]["< 6000 DJC"]
        df.loc[grand_multilogement_mask, 'wall_assembly_r'] = standard_values[standard_name]["Grand multilogement"]
    else:
        df.loc[regions_6000DJCplus_mask, 'wall_assembly_r'] = standard_values[standard_name][">= 6000 DJC"]
        df.loc[regions_6000DJCmoins_mask, 'wall_assembly_r'] = standard_values[standard_name]["< 6000 DJC"]

    return df

def added_roof_or_ceiling_insulation(df: pd.DataFrame, insulation_added: float):
    """
    Apply the new roof or ceiling insulation value based on the added insulation.

    Args:
        df (DataFrame): The DataFrame containing building data.
        insulation_added (float): The amount of insulation added (R-value).

    Returns:
        df (DataFrame): The DataFrame with updated roof or ceiling insulation values.

    """
    # Conditions
    mask_ConditionedAttic = df['geometry_attic_type'] == "ConditionedAttic"
    mask_NonConditionedAttic = ~mask_ConditionedAttic
    
    # Apply the added insulation to the roof or ceiling assembly R-value based on the attic type
    df.loc[mask_ConditionedAttic, 'roof_assembly_r'] = df.loc[mask_ConditionedAttic, 'roof_assembly_r'] + insulation_added
    df.loc[mask_NonConditionedAttic, 'ceiling_assembly_r'] = df.loc[mask_NonConditionedAttic, 'ceiling_assembly_r'] + insulation_added

    return df

def window_properties(df: pd.DataFrame, improvement_rate_uvalue: float, improvement_rate_shgc: float):
    """
    Apply the new window properties based on the improvement rates.

    Args:
        df (DataFrame): The DataFrame containing building data.
        improvement_rate_uvalue (float): The percentage improvement rate for U-value (fraction).
        improvement_rate_shgc (float): The percentage improvement rate for SHGC (fraction).

    Returns:
        df (DataFrame): The DataFrame with updated window properties.

    """
    df['window_ufactor'] = df['window_ufactor'] * (1 - improvement_rate_uvalue)
    df['window_shgc'] = df['window_shgc'] * (1 + improvement_rate_shgc)

    return df

def air_leakage(df: pd.DataFrame, improvement_rate: float):
    """
    Apply the new air leakage value based on the improvement rate.

    Args:
        df (DataFrame): The DataFrame containing building data.
        improvement_rate (float): The percentage improvement rate (0-100).

    Returns:
        df (DataFrame): The DataFrame with updated air leakage values.

    """
    df['air_leakage_value'] = df['air_leakage_value'] * (1 - improvement_rate)

    return df

def decrease_heating_setpoint(df: pd.DataFrame, decrease_value: float):
    """
    Apply the decrease in heating setpoint temperature based on the decrease value.

    Args:
        df (DataFrame): The DataFrame containing building data.
        decrease_value (float): The amount to decrease the heating setpoint temperature (in degrees Celsius).
        
    Returns:		
            df (DataFrame): The DataFrame with updated heating setpoint temperatures.

    """
    # For each tuple in the "Heating Setpoint" column, decrease the 3 values 
    # (Tjour, Tsoir, Tnuit) of each tuple by the decrease_value
    listTuples = df['Heating Setpoint'].tolist()
    newListTuples = []
    for ituple in listTuples:
        ituple = eval(ituple) # Convert the string representation of the tuple to an actual tuple
        newTuple = (ituple[0] - decrease_value, 
                    ituple[1] - decrease_value, 
                    ituple[2] - decrease_value)
        newListTuples.append(newTuple.__str__()) # Convert the new tuple back to a string representation to store in the DataFrame
    
    # Update the "Heating Setpoint" column with the new list of tuples
    df['Heating Setpoint'] = newListTuples

    return df

def add_ashp(df: pd.DataFrame, ashp_seer2 = 17.0, ashp_hspf2 = 8.5):
    """
    Add an air source heat pump (ASHP) to the building data based on the provided SEER2 and HSPF2 values.

    Args:
        df (DataFrame): The DataFrame containing building data.
        ashp_seer2 (float): The SEER2 value of the ASHP.
        ashp_hspf2 (float): The HSPF2 value of the ASHP.
    Returns:
        df (DataFrame): The DataFrame with the added ASHP information.

    """
    # Set the heating system type to "ASHP" and add new columns for ASHP properties to the DataFrame
    df['Chauffage_Logement'] = "ASHP"
    df['heating_system_type'] = "none"
    df['heating_system_heating_efficiency'] = 0
    df['heating_system_fraction_heat_load_served'] = 0
    df['cooling_system_type'] = 'none'
    df['cooling_system_fraction_cool_load_served'] = 0
    df['heat_pump_type'] = 'air-to-air'
    df['heat_pump_heating_efficiency_type'] = 'HSPF2'
    df['heat_pump_heating_efficiency'] = ashp_hspf2
    df['heat_pump_cooling_efficiency_type'] = 'SEER2'
    df['heat_pump_cooling_efficiency'] = ashp_seer2
    df['heat_pump_sizing_methodology'] = 'MaxLoad'
    df['heat_pump_fraction_heat_load_served'] = 1
    df['heat_pump_fraction_cool_load_served'] = 1
    df['heat_pump_backup_type'] = 'integrated'
    df['heat_pump_backup_fuel'] = 'electricity' # if fully electric, otherwise fuel oil when dual-energy ('fuel oil')
    df['heat_pump_backup_heating_efficiency'] = 1 # if fully electric, otherwise 0.8 when dual-energy
    df['heat_pump_heating_capacity_retention_fraction'] = 0.7 # only for air-to-air heat pumps
    df['heat_pump_heating_capacity_retention_temp'] = 5 # only for air-to-air heat pumps
    df['heat_pump_is_ducted'] = True
    df['heat_pump_compressor_lockout_temp'] = 5 # if dual-fuel system, then 10.4 F
    df['heat_pump_cooling_compressor_type'] = 'variable speed' # "single stage" or "two stage" or "variable speed" for GSHPs
    
    # Adjustments for dual-energy cases
    if "Bi-energie" in df['Source_Energie_Chauf'].values:
        df[df['Source_Energie_Chauf'] == "Bi-energie"]['heat_pump_backup_fuel'] = 'fuel oil'
        df[df['Source_Energie_Chauf'] == "Bi-energie"]['heat_pump_backup_heating_efficiency'] = 0.8
        df[df['Source_Energie_Chauf'] == "Bi-energie"]['heat_pump_compressor_lockout_temp'] = 10.4
    
    return df

def add_gshp(df: pd.DataFrame, gshp_eer = 20.5, gshp_cop = 4.0):
    """
    Add a ground source heat pump (GSHP) to the building data based on the provided EER and COP values.

    Args:
        df (DataFrame): The DataFrame containing building data.
        gshp_eer (float): The EER value of the GSHP.
        gshp_cop (float): The COP value of the GSHP.
    Returns:
        df (DataFrame): The DataFrame with the added GSHP information.

    """
    # Set the heating system type to "GSHP" and add new columns for GSHP properties to the DataFrame
    df['Chauffage_Logement'] = "GSHP"
    df['heating_system_type'] = "none"
    df['heating_system_heating_efficiency'] = 0
    df['heating_system_fraction_heat_load_served'] = 0
    df['cooling_system_type'] = 'none'
    df['cooling_system_fraction_cool_load_served'] = 0
    df['heat_pump_type'] = 'ground-to-air'
    df['heat_pump_heating_efficiency_type'] = 'COP'
    df['heat_pump_heating_efficiency'] = gshp_cop
    df['heat_pump_cooling_efficiency_type'] = 'EER'
    df['heat_pump_cooling_efficiency'] = gshp_eer
    df['heat_pump_sizing_methodology'] = 'MaxLoad'
    df['heat_pump_fraction_heat_load_served'] = 1
    df['heat_pump_fraction_cool_load_served'] = 1
    df['heat_pump_backup_type'] = 'none' # can be "integrated"
    df['heat_pump_backup_fuel'] = 'electricity' # if fully electric, otherwise fuel oil when dual-energy ('fuel oil')
    df['heat_pump_backup_heating_efficiency'] = 1 # if fully electric, otherwise 0.8 when dual-energy
    df['heat_pump_is_ducted'] = True
    df['heat_pump_cooling_compressor_type'] = 'variable speed' # "single stage" or "two stage" or "variable speed" for GSHPs
    df['geothermal_loop_configuration'] = 'vertical'
    #df['geothermal_loop_grout_type'] = 'standard' # or 'thermally_enhanced'
    #df['geothermal_loop_pipe_type'] = 'standard' # or 'thermally_enhanced'
    #df['simulation_control_ground_to_air_heat_pump_model_type'] = 'standard' # or 'experimental'

    return df

def add_mshp(df: pd.DataFrame, mshp_seer2 = 21.0, mshp_hspf2 = 10.0):
    """
    Add a mini-split heat pump (MSHP) to the building data based on the provided SEER2 and HSPF2 values.

    Args:
        df (DataFrame): The DataFrame containing building data.
        mshp_seer2 (float): The SEER2 value of the MSHP.
        mshp_hspf2 (float): The HSPF2 value of the MSHP.
    Returns:	
        df (DataFrame): The DataFrame with the added MSHP information.

    """
    # Set the heating system type to "MSHP" and add new columns for MSHP properties to the DataFrame
    df['Chauffage_Logement'] = "MSHP"
    df['heating_system_type'] = "none"
    df['heating_system_heating_efficiency'] = 0
    df['heating_system_fraction_heat_load_served'] = 0
    df['cooling_system_type'] = 'none'
    df['cooling_system_fraction_cool_load_served'] = 0
    df['heat_pump_type'] = 'mini-split'
    df['heat_pump_heating_efficiency_type'] = 'HSPF2'
    df['heat_pump_heating_efficiency'] = mshp_hspf2
    df['heat_pump_cooling_efficiency_type'] = 'SEER2'
    df['heat_pump_cooling_efficiency'] = mshp_seer2
    df['heat_pump_sizing_methodology'] = 'ACCA'
    df['heat_pump_fraction_heat_load_served'] = 1
    df['heat_pump_fraction_cool_load_served'] = 1
    df['heat_pump_backup_type'] = 'integrated' 
    df['heat_pump_backup_fuel'] = 'electricity' # if fully electric, otherwise fuel oil when dual-energy ('fuel oil')
    df['heat_pump_backup_heating_efficiency'] = 1 # if fully electric, otherwise 0.8 when dual-energy
    df['heat_pump_heating_capacity_retention_fraction'] = 0.7 # only for air-to-air heat pumps
    df['heat_pump_heating_capacity_retention_temp'] = 5 # only for air-to-air heat pumps
    df['heat_pump_is_ducted'] = False
    df['heat_pump_compressor_lockout_temp'] = 5 # if dual-fuel system, then 10.4 F
    df['heat_pump_cooling_compressor_type'] = 'variable speed' # "single stage" or "two stage" or "variable speed" for GSHPs

    # Adjustments for dual-energy cases
    if "Bi-energie" in df['Source_Energie_Chauf'].values:
        df[df['Source_Energie_Chauf'] == "Bi-energie"]['heat_pump_backup_fuel'] = 'fuel oil'
        df[df['Source_Energie_Chauf'] == "Bi-energie"]['heat_pump_backup_heating_efficiency'] = 0.8
        df[df['Source_Energie_Chauf'] == "Bi-energie"]['heat_pump_compressor_lockout_temp'] = 10.4

    return df

# Function to apply upgrades to the building data
def apply_upgrades(self,building_data):
    """
    Apply upgrades to the building data based on the configuration constraints.

    Args:
        building_data (dataframe): The building data to which upgrades will be applied.

    Returns:
        building_data (dataframe): The updated building data with applied upgrades.
    """
    # Check if upgrade settings are defined
    if self.cfg["UPGRADES_SETTINGS"] is None:
        return None

    upgrades = self.cfg["UPGRADES_SETTINGS"]
        
    # Iterate through each set of upgrades defined in the configuration
    i = 0
    building_data_init = building_data.copy()
    building_data_upgrades = pd.DataFrame()
    for set_of_measures in upgrades.keys():
        i += 1
        # Apply filters to select the targeted buildings for the upgrades
        filters = upgrades[set_of_measures]["Filters"]
        i_building_data = apply_filters(building_data_init, filters)
        # Apply the adoption rate to select buildings for upgrades
        adoption_rate = upgrades[set_of_measures]["Adoption rate"]
        i_building_data = i_building_data.sample(frac=adoption_rate, replace=False, axis=0,
                                                 random_state=self.cfg["SEED"])
        # Define a new building_id in the dataframe
        i_building_data['building_id'] = i_building_data['building_id'].astype(str)+"_SetOfMeasures"+str(i)
        i_building_data['upgrading_name'] = upgrades[set_of_measures]["Name"]
        for measure in upgrades[set_of_measures]["Upgrades"].keys():
            if measure == "Wall insulation":
                improvement_rate = upgrades[set_of_measures]["Upgrades"][measure]["improvement_rate"]
                i_building_data = wall_insulation(i_building_data, improvement_rate)
            elif measure == "Window properties":
                improvement_rate_uvalue = upgrades[set_of_measures]["Upgrades"][measure]["improvement_rate_uvalue"]
                improvement_rate_shgc = upgrades[set_of_measures]["Upgrades"][measure]["improvement_rate_shgc"]
                i_building_data = window_properties(i_building_data, improvement_rate_uvalue, improvement_rate_shgc)
            elif measure == "Air leakage":
                improvement_rate = upgrades[set_of_measures]["Upgrades"][measure]["improvement_rate"]
                i_building_data = air_leakage(i_building_data, improvement_rate)
            elif measure == "Set wall insulation to standard":
                standard_name = upgrades[set_of_measures]["Upgrades"][measure]["standard_name"]
                i_building_data = set_wall_insulation_to_standard(i_building_data, standard_name)
            elif measure == "Added roof or ceiling insulation":
                insulation_added = upgrades[set_of_measures]["Upgrades"][measure]["insulation_added"]
                i_building_data = added_roof_or_ceiling_insulation(i_building_data, insulation_added)
            elif measure == "Set ceiling insulation":
                new_insulation_value = upgrades[set_of_measures]["Upgrades"][measure]["insulation_set"]
                i_building_data = set_ceiling_insulation(i_building_data, new_insulation_value)
            elif measure == "Heating setpoint decrease":
                decrease_value = upgrades[set_of_measures]["Upgrades"][measure]["decrease_value"]
                i_building_data = decrease_heating_setpoint(i_building_data, decrease_value)
            elif measure == "ASHP":
                seer2 = upgrades[set_of_measures]["Upgrades"][measure]["seer2"]
                hspf2 = upgrades[set_of_measures]["Upgrades"][measure]["hspf2"]
                i_building_data = add_ashp(i_building_data, seer2, hspf2)
            elif measure == "GSHP":
                eer = upgrades[set_of_measures]["Upgrades"][measure]["eer"]
                cop = upgrades[set_of_measures]["Upgrades"][measure]["cop"]
                i_building_data = add_gshp(i_building_data, eer, cop)
            elif measure == "MSHP":
                seer2 = upgrades[set_of_measures]["Upgrades"][measure]["seer2"]
                hspf2 = upgrades[set_of_measures]["Upgrades"][measure]["hspf2"]
                i_building_data = add_mshp(i_building_data, seer2, hspf2)
        # Concatenate the modified building data with the original data
        building_data_upgrades = pd.concat([building_data_upgrades, i_building_data], ignore_index=True)
    
    return building_data_upgrades