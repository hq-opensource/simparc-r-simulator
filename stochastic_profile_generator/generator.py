# -*- coding: utf-8 -*-

import pandas as pd
import numpy as np
import uuid
from stochastic_profile_generator.ev.ev_profile_generator import generateSingleAnnuelVEHourlyProfile
from stochastic_profile_generator.pool.ModelePompePiscine_01 import TPompePiscine
from stochastic_profile_generator.pool.ModeleChauffePiscine_01 import TChauffePiscine
from stochastic_profile_generator.pool.ModeleChauffePiscine_01 import Tmaison_pool_heater
from stochastic_profile_generator.hvac.temperature_setpoint_model import Tsetpoint
from stochastic_profile_generator.utils.load_meteo_epw import MeteoEPW
from stochastic_profile_generator.spa.spa_model import Tmaison, TSPA

class profile_generator(object):
    def __init__(self,cfg):
        self._uid = uuid.uuid4()
        self.cfg = cfg
        
    def ev(self,EV_Type, year, rng):
        return generateSingleAnnuelVEHourlyProfile(EV_Type, year, rng)
    
    def spa(self,epw_weather_filepath, param_spa):
        """
        SPA Profile Generator

        :param epw_weather_filepath:
        :param param_spa: Dictionary containing SPA parameters
        :return: Annual energy use in kWh and power profile array
        """

        # Load weather data
        M, simulation_timesteps = self.load_epw_weather_data(epw_weather_filepath)

        # Create and run simulation
        spa_obj = TSPA(M, {'Type': 'SPA', **param_spa})
        spa_obj.Calcul_Equipement(simulation_timesteps)

        # Calculate metrics
        power_profile = np.array(spa_obj.Puissance.data)
        annual_energy_use_kWh = power_profile.mean() * 8760 / 1000

        return annual_energy_use_kWh, power_profile
    
    def load_epw_weather_data(self, epw_weather_filepath,**kwargs):
        """
        Load EPW weather data into MeteoEPW object.

        Args:
            epw_weather_filepath: Full path to the EPW weather file

        Returns:
            MeteoEPW object with loaded weather data
        """
        # Load weather data
        DateDebut = np.datetime64(f'{self.cfg["SIMULATION_YEAR"]}-01-01T00:00:00')
        DateFin = np.datetime64(f'{self.cfg["SIMULATION_YEAR"]}-12-31T23:00:00')
        TimeStep = str(self.cfg["SIMULATION_TIMESTEP"]) + 'min'

        obMeteo = MeteoEPW(MeteoName=epw_weather_filepath, DateDebut=DateDebut, DateFin=DateFin, TimeStep=TimeStep)
        obMeteo.CalculMeteo()

        # Set up time parameters
        grMeteo = obMeteo.Donnees_Meteo.Grp_data
        flDtSec = (grMeteo['DryBulb'].time[1] - grMeteo['DryBulb'].time[0]).total_seconds()
        flDtHeure = flDtSec / 3600

        # Create M object
        if "M_FLAG_POOL_HEATER" in kwargs and kwargs["M_FLAG_POOL_HEATER"] is True:
            M = Tmaison_pool_heater()
        else:
            M = Tmaison()
        M.dt = flDtHeure
        M.Donnees_Meteo = grMeteo

        # Create time simulation array
        #simulation_timesteps = pd.date_range(start=DateDebut, end=DateFin, freq=TimeStep).tolist()
        simulation_timesteps = list(obMeteo.weather_data.index)

        return M, simulation_timesteps

    def pool_pump(self,**kwargs):
        """
        Generate a single pool pump power profile.

        Parameters
        ----------
        pool_type : str
            Pool type ('HT' = above-ground, 'CR' = in-ground)
        operating_mode : str
            Operating mode ('AvecMinuterie' = with timer, 'SansMinuterie' = without timer)

        Returns
        -------
        annual_kwh : float
    		Annual energy consumption in kWh
    	power_profile : np.ndarray
            Power profile array in watts (~105,120 points for 5-minute intervals)

        Author: Saeid Hosseini
        Date: October 2025

        """
        # Mapping and defining pool type and operating mode to expected strings
        pool_type_mapping = {
            'Hors_Terre': 'HT',
            'Creusee_Exterieur': 'CR',
            'Creusee_Interieur': 'CR'
        }
        operating_mode_mapping = {
            'Non': 'SansMinuterie',
            'Oui': 'AvecMinuterie'
        }
        pool_type = pool_type_mapping.get(kwargs["pool_type"], 'HT')
        operating_mode = operating_mode_mapping.get(kwargs["operating_mode"], 'SansMinuterie')

        # Validate inputs
        if pool_type not in ['HT', 'CR']:
            raise ValueError(f"pool_type must be 'HT' or 'CR', got: {pool_type}")

        if operating_mode not in ['AvecMinuterie', 'SansMinuterie']:
            raise ValueError(f"operating_mode must be 'AvecMinuterie' or 'SansMinuterie', got: {operating_mode}")

        # Create configuration
        pool_config = {
            'Type': 'POOLPUMP',
            'TypePiscine': pool_type,
            'ModeOperPiscine': operating_mode
        }

        # Create time simulation (full year at 5-minute intervals)
        DateDebut = np.datetime64(f'{self.cfg["SIMULATION_YEAR"]}-01-01T00:00:00')
        DateFin = np.datetime64(f'{self.cfg["SIMULATION_YEAR"]}-12-31T23:59:00')
        TimeStep = str(self.cfg["SIMULATION_TIMESTEP"]) + 'min'

        time_simu = pd.date_range(start=DateDebut, end=DateFin, freq=TimeStep).tolist()

        # Create pool pump object
        pool_pump = TPompePiscine(0, pool_config)

        # CRITICAL FIX: Model doesn't properly read string parameters from config
        # Must manually override these attributes (discovered in pomppiscine_generator_analysis.ipynb)
        pool_pump.stTypePiscine = pool_type
        pool_pump.stModeOperPiscine = operating_mode

        # Run simulation
        pool_pump.Calcul_Equipement(time_simu)

        # Compute annual energy consumption
        annual_kwh = np.sum(np.array(pool_pump.Puissance.data) * (self.cfg["SIMULATION_TIMESTEP"] / 60) / 1000)

        # Return annual energy consumption and power profile (same as SPA)
        return annual_kwh, np.array(pool_pump.Puissance.data)

    def pool_heater(self,epw_weather_filepath, **kwargs):
        """
        Generate a single pool heater power profile from location, scenario, and pool parameters.

        Author: Saeid Hosseini
        Date: October 2025
        """
        # Map heater_type string to expected integer - TO BE MODIFIED...
        # "electric resistance","gas fired","heat pump"
        heater_type_mapping = {
            'heat pump': 1,
            'gas fired': 2,
            'electric resistance': 3,
            'solar': 4,
            'other': 5
        }
        heater_type = heater_type_mapping.get(kwargs["heater_type"], 1)

        # Map with_cover string to expected boolean
        with_cover_mapping = {
            'Oui': True,
            'Non': False
        }
        with_cover = with_cover_mapping.get(kwargs["with_cover"], False)

        # Map pool_type string to expected integer
        pool_type_mapping = {
            'Hors_Terre': 2,
            'Creusee_Exterieur': 1,
            'Creusee_Interieur': 1
        }
        pool_type = pool_type_mapping.get(kwargs["pool_type"], 2)

        # Randomly select pool_surface
        # Surface category: 1-7 (size categories in m²)
        # 1=<20m², 2=20-28m², 3=28-37m², 4=37-47m², 5=47-59m², 6=59-72m², 7=≥72m²
        occurances = np.array([5, 10, 20, 25, 20, 15, 5])
        pool_surface = np.random.choice([1, 2, 3, 4, 5, 6, 7], p=occurances / occurances.sum())

        # Validate scenario
        # if scenario not in ['2020s', '2050s', '2080s']:
        #     raise ValueError(f"scenario must be '2020s', '2050s', or '2080s', got: {scenario}")

        # Validate inputs
        if pool_type not in [1, 2]:
            raise ValueError(f"pool_type must be 1 (CR/in-ground) or 2 (HT/above-ground), got: {pool_type}")

        if pool_surface not in [1, 2, 3, 4, 5, 6, 7]:
            raise ValueError(f"pool_surface must be 1-7, got: {pool_surface}")

        if heater_type not in [1, 2, 3, 4, 5]:
            raise ValueError(
                f"heater_type must be 1-5 (1=Heat pump, 2=Gas, 3=Electric, 4=Solar, 5=Other), got: {heater_type}")

        # Create pool configuration - 4 parameters
        # Model will auto-size heater capacity based on pool type and surface
        pool_config = {
            'Type': 'POOLHEATER',
            'PISC_TYPE': pool_type,
            'PISC_SURFACE': pool_surface,
            'PISC_TOILE': 2 if with_cover else 1,
            'PISC_CHAUFTYPE': heater_type,
        }

        # Load weather data (following SPA pattern - year auto-detected inside)
        M, time_simu = self.load_epw_weather_data(epw_weather_filepath, M_FLAG_POOL_HEATER=True)

        pool_heater = TChauffePiscine(M, pool_config)
        pool_heater.Calcul_Equipement(time_simu)

        # Run simulation for pool heater
        time_array = np.array(pool_heater.Puissance.time)
        power_array = np.array(pool_heater.Puissance.data)

        # Run simulation and return time + power profile (following SPA pattern)
        return time_array, power_array

    def temperature_setpoint(self,epw_weather_filepath,**kwargs):
        # Load weather data
        M, simulation_timesteps = self.load_epw_weather_data(epw_weather_filepath)

        # Create and run simulation
        kwargs['Type'] = 'Temperature_Setpoint_Profile_Generator'
        Tsetpoint_obj = Tsetpoint(M, kwargs)
        Tsetpoint_obj.Calcul_consignes(simulation_timesteps)

        Tc = np.array(Tsetpoint_obj.get_Tconsigne_Chauffage())  # Temperature
        Pc = np.array(Tsetpoint_obj.get_Pconsigne_Chauffage())  # Profile
        Time = np.array(Tsetpoint_obj.get_Time())  # Time
        return Time, Tc, Pc

def main():
    gen = profile_generator(r"C:\Users\Gilbert\Desktop\SCR\LTE-OpenStudioCLI-Test\project.yaml")
    gen.test()

if __name__ == "__main__":
    main()