# -*- coding: utf-8 -*-

# Import libraries
import os
import json
import numpy as np
import pandas as pd
import random

# Import local libraries
from stochastic_profile_generator.generator import profile_generator

# Class to define a building and its methods/attributes
class Building:
    """
    The current class Building is used to define a building based on inputs defined in the
    OpenStudio-HPXML module developed by NREL. This class contains multiple methods, including:
    - __init__: Initialize the Building object with HPXML and non-HPXML arguments.
    - create_osw: Create an OpenStudio Workflow (OSW) file based on the building's arguments.
    - Other methods will be added later to extend the functionality of the Building class.

    """
    def __init__(self, building_data: dict, cfg):
        """
        Initialize the Building object with HPXML and non-HPXML arguments.

        Args:
            building_data (dict): A dictionary containing the HPXML and non-HPXML arguments for the building.
            
        """
        # Check if hpxml_args is a dictionary
        if not isinstance(building_data, dict):
            raise TypeError("building_data must be a dictionary")

        self.hpxml_args = building_data['hpxml_args']
        self.non_hpxml_args = building_data['non_hpxml_args']
        self.cfg = cfg
        self.prof_gen = profile_generator(cfg)

    def generate_stochastic_profile(self, building_dir: str):
        """
        Generate stochastic profiles based on the building's HPXML arguments.
        Currently implemented:
        - Heating setpoint profile generation
        - EV profile generation
        - Pool profile generation
        - Spa profile generation
        Args:
            building_dir (str): The directory where the building simulation results are stored.

        Returns:
            None
        """
        # Define seed for reproducibility
        seed_value = self.non_hpxml_args.get('seed')
        if seed_value is not None:
            random.seed(seed_value)
            np.random.seed(seed_value)
            rng = np.random.default_rng(seed_value)
        else:
            rng = np.random.default_rng()
        
        ########################################################################################
        # Heating setpoint profile if needed
        ########################################################################################
        if self.non_hpxml_args.get('Heating Setpoint',False) == False:
            # No need to generate heating setpoint profile
            pass

        else:
            self.non_hpxml_args['stochastic_heating_setpoint'] = True
            # Generate a new Heating Setpoint profile for the building
            params = {"Heating Setpoint": self.non_hpxml_args['Heating Setpoint'],
                    "Tconsignes_chauffage_H1": self.non_hpxml_args['Tconsignes_chauffage_H1'],
                    "Tconsignes_chauffage_H2": self.non_hpxml_args['Tconsignes_chauffage_H2'],
                    "Tconsignes_chauffage_H3": self.non_hpxml_args['Tconsignes_chauffage_H3'],
                    "Tconsignes_chauffage_H4": self.non_hpxml_args['Tconsignes_chauffage_H4']}

            Time, Temp_Heating_Setpoint, Profil_Heating_Setpoint = self.prof_gen.temperature_setpoint(self.hpxml_args['weather_station_epw_filepath'],**params)
            deltat = (Time[1]-Time[0]).total_seconds()/60
            time_min = np.arange(0,len(Time)*deltat,deltat)

            # save as a csv the Heating Setpoint profile into building_dir
            df_temp_profile = pd.DataFrame({'time_min': time_min,
                                            'heating_setpoint_C': Temp_Heating_Setpoint,#C
                                            'heating_setpoint_F': Temp_Heating_Setpoint * 9/5 + 32,#F
                                            "profil_heating_setpoint": Profil_Heating_Setpoint})
            df_temp_profile.to_csv(str(building_dir / 'stochastic_profile_heating_setpoint.csv'),index=False)

            # define a cooling setpoint 2F higher than heating setpoint
            self.hpxml_args['hvac_control_cooling_weekday_setpoint'] = str(df_temp_profile['heating_setpoint_F'].max() + 2)
            self.hpxml_args['hvac_control_cooling_weekend_setpoint'] = self.hpxml_args['hvac_control_cooling_weekday_setpoint']
            pass

        ########################################################################################
        # Generate stochastic profile for ev if present
        ########################################################################################
        if self.hpxml_args.get('misc_plug_loads_vehicle_present',False) == False:
            # No ev --> no need to generate ev profile
            pass

        else:
            # EV profile generation
            mapping_nb_ev = {'Une': 1, 'Deux': 2, 'Trois': 3}
            nb_bev = mapping_nb_ev.get(self.non_hpxml_args.get('Vehicule_Presence','Aucun').split('_')[0],0)
            nb_phev = mapping_nb_ev.get(self.non_hpxml_args.get('Vehicule_Presence','Aucun_Aucun_Aucun').split('_')[2],0)
            # Generate a profile for each EV and sum them up
            df_evs = pd.DataFrame({})
            for i in range(nb_bev):
                # Generate hourly bev profiles
                df_evs['ev_bev_'+str(i+1)+'_kW'] = self.prof_gen.ev('Battery Electric', self.cfg["SIMULATION_YEAR"], rng)
                pass
            for i in range(nb_phev):
                # Generate hourly phev profiles
                df_evs['ev_phev_'+str(i+1)+'_kW'] = self.prof_gen.ev('Hybrid', self.cfg["SIMULATION_YEAR"], rng)

            df_ev = df_evs.sum(axis=1)
            self.hpxml_args['misc_plug_loads_vehicle_annual_kwh'] = df_ev.sum()
            self.hpxml_args['misc_plug_loads_vehicle_usage_multiplier'] = 1.0
            # save as a csv the ev power profile into building_dir
            df_power_profile = pd.DataFrame({'time_min': np.arange(0,len(df_ev)*60,60), 
                                             'power_W': df_ev.values * 1000})
            df_power_profile.to_csv(str(building_dir / 'stochastic_profile_ev_W.csv'),index=False)
            pass

        ########################################################################################
        # Generate stochastic profile for pool if present
        ########################################################################################
        if self.hpxml_args.get('pool_present',False) == False:
            # No pool --> no need to generate pool profile
            pass

        else:
            # Generate a new pool pump profile for the building
            annual_energy_use_pump_kWh, power_profile_pump_array = self.prof_gen.pool_pump(
                pool_type=self.non_hpxml_args.get('Piscine_Type','HT'),
                operating_mode=self.non_hpxml_args.get('Piscine_Minuterie','Non'))
            self.hpxml_args['pool_pump_annual_kwh'] = annual_energy_use_pump_kWh
            self.hpxml_args['pool_pump_usage_multiplier'] = 1
            # save as a csv the pool pump power profile into building_dir
            df_power_profile = pd.DataFrame({'time_min': np.arange(0,len(power_profile_pump_array)*self.cfg["SIMULATION_TIMESTEP"],
                                                                   self.cfg["SIMULATION_TIMESTEP"]),
                                             'power_W': power_profile_pump_array})
            df_power_profile.to_csv(str(building_dir / 'stochastic_profile_pool_pump_W.csv'),index=False)
            # Generate a new pool heater profile for the building
            if self.non_hpxml_args.get('Piscine_Chauffee','Non') != 'Oui':
                pass
            else:
                time_array, power_profile_heater_array = self.prof_gen.pool_heater(self.hpxml_args['weather_station_epw_filepath'],
                    pool_type=self.non_hpxml_args.get('Piscine_Type','Hors_Terre'),
                    with_cover=self.non_hpxml_args.get('Piscine_Toile','Oui'),
                    heater_type=self.hpxml_args.get('pool_heater_type','electric resistance'))
                self.hpxml_args['pool_heater_annual_kwh'] = np.sum(power_profile_heater_array * self.cfg["SIMULATION_TIMESTEP"] / 60 / 1000)
                self.hpxml_args['pool_heater_annual_therm'] = self.hpxml_args['pool_heater_annual_kwh'] / 29.3  # convert kWh to therms
                self.hpxml_args['pool_heater_usage_multiplier'] = 1
                # save as a csv the pool heater power profile into building_dir
                beginning_min = (time_array[0]-np.datetime64(f'{self.cfg["SIMULATION_YEAR"]}-01-01T00:00:00')).total_seconds() / 60
                time_min_array = np.arange(beginning_min, 
                                           beginning_min+(len(time_array)*self.cfg["SIMULATION_TIMESTEP"]),
                                           self.cfg["SIMULATION_TIMESTEP"])
                df_power_profile = pd.DataFrame({'time_min': time_min_array, 
                                                'power_W': power_profile_heater_array})
                df_power_profile.to_csv(str(building_dir / 'stochastic_profile_pool_heater_W.csv'),index=False)
                pass

        ########################################################################################
        # Generate stochastic profile for spa if present
        ########################################################################################
        if self.hpxml_args.get('permanent_spa_present',False) == False:
            # No spa --> no need to generate spa profile
            pass

        else:
            # Generate a new spa profile for the building
            param_spa = {}
            for p in ['Spa_Presence',
                      'Spa_Logement',
                      'Spa_Saison',
                      'Spa_Utilisation_SaisonChaude',
                      'Spa_Utilisation_SaisonFroide',
                      'Spa ChaufType']:
                if p in self.non_hpxml_args:
                    param_spa[p] = self.non_hpxml_args[p]

            annual_energy_use_kWh, power_profile_array = self.prof_gen.spa(self.hpxml_args['weather_station_epw_filepath'], param_spa)
            self.hpxml_args['permanent_spa_heater_annual_kwh'] = annual_energy_use_kWh
            self.hpxml_args['permanent_spa_heater_annual_therm'] = annual_energy_use_kWh / 29.3  # convert kWh to therms
            self.hpxml_args['permanent_spa_pump_annual_kwh'] = 0
            # save as a csv the spa power profile into building_dir
            df_power_profile = pd.DataFrame({'time_min': np.arange(0,len(power_profile_array)*self.cfg["SIMULATION_TIMESTEP"],
                                                                   self.cfg["SIMULATION_TIMESTEP"]),
                                             'power_W': power_profile_array})
            df_power_profile.to_csv(str(building_dir / 'stochastic_profile_spa_W.csv'),index=False)
            pass
        pass

    def create_osw(self, project_dir, building_dir):
        """
        Create an OpenStudio Workflow (OSW) file based on the building's HPXML arguments.

        Args:
            project_dir (str): The directory where the project is located.
            building_dir (str): The directory where the building's OSW file will be created.

        Returns:
            None
        """
        # Initialize the content of a OSW (OpenStudio Workflow) file
        self.osw_content = {}

        # Define the path to the measures
        self.osw_content['measure_paths'] = [os.path.join(project_dir, self.cfg["MEASURES_PATH"])]
        
        # Initialize the list of steps in the OSW content
        self.osw_content['steps'] = []

        # Step 1 - BuildResidentialHPXML
        step1 = {
            'measure_dir_name': 'BuildResidentialHPXML',
            'arguments': self.hpxml_args
        }
        self.osw_content['steps'].append(step1)

        # Step 2 - BuildResidentialScheduleFile
        step2 = {
            'measure_dir_name': 'BuildResidentialScheduleFile',
            'arguments': {
                "hpxml_path": str(building_dir / "built.xml"),
                "output_csv_path": str(building_dir / "stochastic.csv"),
                "hpxml_output_path": str(building_dir / "built-stochastic-schedules.xml"),
                "schedules_random_seed": self.non_hpxml_args.get('seed')
            }}
        self.osw_content['steps'].append(step2)

        # Step 3 - ModifyStochasticFilePython - Modify the stochastic file generated in Step 2
        step3 = {
            'measure_dir_name': 'ModifyStochasticFilePython',
            'arguments': {
                "csv_path_stochastic": str(building_dir / "stochastic.csv"),
                "csv_path_spa": str(building_dir / "stochastic_profile_spa_W.csv"),
                "csv_path_pool_heater": str(building_dir / "stochastic_profile_pool_heater_W.csv"),
                "csv_path_pool_pump": str(building_dir / "stochastic_profile_pool_pump_W.csv"),
                "csv_path_ev": str(building_dir / "stochastic_profile_ev_W.csv"),
                "csv_path_heating_setpoint": str(building_dir / "stochastic_profile_heating_setpoint.csv"),
                "results_dir": os.path.join(project_dir, self.cfg["RESULTS_PATH"]),
                "spa_presence": self.hpxml_args.get('permanent_spa_present',False),
                "pool_presence": self.hpxml_args.get('pool_present',False),
                "pool_heater_type": self.hpxml_args.get('pool_heater_type','none'),
                "ev_presence": self.hpxml_args.get('misc_plug_loads_vehicle_present',False),
                "stochastic_heating_setpoint": self.non_hpxml_args.get('stochastic_heating_setpoint',False),
                "building_id": str(self.non_hpxml_args.get('building_id', "Building_Unknown")),
                "timestep": self.cfg["SIMULATION_TIMESTEP"]
            }}
        self.osw_content['steps'].append(step3)

        # Step 4 - HPXMLtoOpenStudio
        step4 = {
            'measure_dir_name': 'HPXMLtoOpenStudio',
            'arguments': {
                "hpxml_path": str(building_dir / "built-stochastic-schedules.xml"),
                "output_dir": "..",
                "output_format": "csv",
                "add_component_loads": self.cfg["ADD_COMPONENT_LOADS"],
                "skip_validation": self.cfg["SKIP_VALIDATION"],
                "debug": self.cfg["DEBUG_MODE"]
            }}
        self.osw_content['steps'].append(step4)

        # Step 5 - ReportSimulationOutput
        step5 = {
            'measure_dir_name': 'ReportSimulationOutput',
            'arguments': {
                "output_format": "csv",
                "include_annual_total_consumptions": self.cfg["INCLUDE_ANNUAL_TOTAL_CONSUMPTIONS"],
                "include_annual_fuel_consumptions": self.cfg["INCLUDE_ANNUAL_FUEL_CONSUMPTIONS"],
                "include_annual_end_use_consumptions": self.cfg["INCLUDE_ANNUAL_END_USE_CONSUMPTIONS"],
                "include_annual_system_use_consumptions": self.cfg["INCLUDE_ANNUAL_SYSTEM_USE_CONSUMPTIONS"],
                "include_annual_emissions": self.cfg["INCLUDE_ANNUAL_EMISSIONS"],
                "include_annual_emission_fuels": self.cfg["INCLUDE_ANNUAL_EMISSION_FUELS"],
                "include_annual_emission_end_uses": self.cfg["INCLUDE_ANNUAL_EMISSION_END_USES"],
                "include_annual_total_loads": self.cfg["INCLUDE_ANNUAL_TOTAL_LOADS"],
                "include_annual_unmet_hours": self.cfg["INCLUDE_ANNUAL_UNMET_HOURS"],
                "include_annual_peak_fuels": self.cfg["INCLUDE_ANNUAL_PEAK_FUELS"],
                "include_annual_peak_loads": self.cfg["INCLUDE_ANNUAL_PEAK_LOADS"],
                "include_annual_component_loads": self.cfg["INCLUDE_ANNUAL_COMPONENT_LOADS"],
                "include_annual_hot_water_uses": self.cfg["INCLUDE_ANNUAL_HOT_WATER_USES"],
                "include_annual_hvac_summary": self.cfg["INCLUDE_ANNUAL_HVAC_SUMMARY"],
                "include_annual_resilience": self.cfg["INCLUDE_ANNUAL_RESILIENCE"],
                "timeseries_frequency": self.cfg["TIMESERIES_FREQUENCY"],
                "include_timeseries_total_consumptions": self.cfg["INCLUDE_TIMESERIES_TOTAL_CONSUMPTIONS"],
                "include_timeseries_fuel_consumptions": self.cfg["INCLUDE_TIMESERIES_FUEL_CONSUMPTIONS"],
                "include_timeseries_end_use_consumptions": self.cfg["INCLUDE_TIMESERIES_END_USE_CONSUMPTIONS"],
                "include_timeseries_system_use_consumptions": self.cfg["INCLUDE_TIMESERIES_SYSTEM_USE_CONSUMPTIONS"],
                "include_timeseries_emissions": self.cfg["INCLUDE_TIMESERIES_EMISSIONS"],
                "include_timeseries_emission_fuels": self.cfg["INCLUDE_TIMESERIES_EMISSION_FUELS"],
                "include_timeseries_emission_end_uses": self.cfg["INCLUDE_TIMESERIES_EMISSION_END_USES"],
                "include_timeseries_hot_water_uses": self.cfg["INCLUDE_TIMESERIES_HOT_WATER_USES"],
                "include_timeseries_total_loads": self.cfg["INCLUDE_TIMESERIES_TOTAL_LOADS"],
                "include_timeseries_component_loads": self.cfg["INCLUDE_TIMESERIES_COMPONENT_LOADS"],
                "include_timeseries_unmet_hours": self.cfg["INCLUDE_TIMESERIES_UNMET_HOURS"],
                "include_timeseries_zone_temperatures": self.cfg["INCLUDE_TIMESERIES_ZONE_TEMPERATURES"],
                "include_timeseries_zone_conditions": self.cfg["INCLUDE_TIMESERIES_ZONE_CONDITIONS"],
                "include_timeseries_airflows": self.cfg["INCLUDE_TIMESERIES_AIRFLOWS"],
                "include_timeseries_weather": self.cfg["INCLUDE_TIMESERIES_WEATHER"],
                "include_timeseries_resilience": self.cfg["INCLUDE_TIMESERIES_RESILIENCE"],
                "timeseries_timestamp_convention": self.cfg["TIMESERIES_TIMESTAMP_CONVENTION"],
                "add_timeseries_dst_column": self.cfg["ADD_TIMESERIES_DST_COLUMN"],
                "add_timeseries_utc_column": self.cfg["ADD_TIMESERIES_UTC_COLUMN"],
                "user_output_variables": self.cfg["USER_OUTPUT_VARIABLES"],
                "user_output_meters": self.cfg["USER_OUTPUT_METERS"],
            }}
        self.osw_content['steps'].append(step5)

        # Write the OSW content to a file
        with open(str(building_dir / 'in.osw'), 'w') as f:
            json.dump(self.osw_content, f, indent=2)

        return