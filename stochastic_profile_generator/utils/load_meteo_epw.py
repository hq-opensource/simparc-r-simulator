# -*- coding: utf-8 -*-
"""
@author: Saeid Hosseini / Enhanced for EPW support

load_meteo_epw.py
EPW (EnergyPlus Weather) file loader for spa and pool heating simulations

"""

#import os
import numpy as np
import pandas as pd
import datetime as dt
import pytz
import math
# Updated import for new project structure
from stochastic_profile_generator.utils.data import Data, Grp_data

class MeteoEPW(object):
    
    def __init__(self,
                 MeteoName='mtl.epw',
                 DateDebut=None,
                 DateFin=None,
                 TimeStep='5T'):
        
        self.MeteoName = MeteoName
        self.DateDebut = DateDebut
        self.DateFin = DateFin
        self.TimeStep = TimeStep
        
        self.local_tz = pytz.timezone('America/Montreal')
        self.nom_station = MeteoName.replace('.epw', '')
    
    def loadFile(self):
        """Load EPW file and convert to pandas DataFrame"""
        #Path_MeteoName = os.path.join(self.PROJECT_DIR, 'data', 'weather_data', self.MeteoName)
        Path_MeteoName = self.MeteoName
        
        # EPW column names (standard EnergyPlus format)
        epw_columns = [
            'Year', 'Month', 'Day', 'Hour', 'Minute', 'DataSource',
            'DryBulb', 'DewPoint', 'RHum', 'Pressure', 'ExtHorRad',
            'ExtDirNormRad', 'HorInfraredRad', 'GHI', 'DirNormRad',
            'DifHorRad', 'GloHorIllum', 'DirNormIllum', 'DifHorIllum',
            'ZenithLum', 'WindDir', 'WindSpeed', 'TotalSkyCover',
            'OpaqueSkyCover', 'Visibility', 'CeilingHeight',
            'PresentWeatherObs', 'PresentWeatherCodes', 'PrecipitableWater',
            'AerosolOpticalDepth', 'SnowDepth', 'DaysSinceLastSnow',
            'Albedo', 'LiquidPrecipitationDepth', 'LiquidPrecipitationQuantity'
        ]
        
        # Read all lines
        with open(Path_MeteoName, 'r') as f:
            lines = f.readlines()
        
        # Find data start (skip header - usually first 8 lines)
        data_start = 0
        for i, line in enumerate(lines):
            # Data lines start with year (4 digits)
            if line.strip() and line.split(',')[0].isdigit() and len(line.split(',')[0]) == 4:
                data_start = i
                break
        
        # Read data lines only
        data_lines = [line.strip() for line in lines[data_start:] if line.strip()]
        
        # Parse data into DataFrame
        data_rows = []
        for line in data_lines:
            # Split by comma and convert to appropriate types
            parts = line.split(',')
            if len(parts) >= 14:  # Ensure minimum required columns
                try:
                    # Convert numeric values, handle missing data
                    row = []
                    for i, part in enumerate(parts[:len(epw_columns)]):
                        if i < 5:  # Year, Month, Day, Hour, Minute
                            row.append(int(float(part)) if part.replace('.','').isdigit() else 0)
                        elif i == 5:  # DataSource (string)
                            row.append(part)
                        else:  # Numeric weather data
                            try:
                                val = float(part) if part and part != '9999' and part != '999999999' else np.nan
                                row.append(val)
                            except:
                                row.append(np.nan)
                    
                    # Pad row if needed
                    while len(row) < len(epw_columns):
                        row.append(np.nan)
                    
                    data_rows.append(row[:len(epw_columns)])
                except:
                    continue
        
        # Create DataFrame
        self.weather_data = pd.DataFrame(data_rows, columns=epw_columns)
        
        # Create datetime index
        timestamps = pd.date_range(start=self.DateDebut, periods=len(self.weather_data), freq='h')
        # timestamps = []
        # for _, row in self.weather_data.iterrows():
        #     try:
        #         # EPW hours are 1-24, convert to 0-23
        #         hour = int(row['Hour']) - 1 if row['Hour'] > 0 else 0
        #         timestamp = dt.datetime(
        #             year=int(row['Year']),
        #             month=int(row['Month']),
        #             day=int(row['Day']),
        #             hour=hour,
        #             minute=int(row['Minute'])
        #         )
        #         timestamps.append(timestamp)
        #     except:
        #         # If datetime creation fails, use previous timestamp + 1 hour
        #         if timestamps:
        #             timestamps.append(timestamps[-1] + dt.timedelta(hours=1))
        #         else:
        #             timestamps.append(dt.datetime(2015, 1, 1, 0, 0))
        
        self.weather_data.index = pd.DatetimeIndex(timestamps)
        
        # Keep only required weather columns and rename for compatibility
        weather_cols = ['DryBulb', 'DewPoint', 'RHum', 'Pressure', 'GHI']
        available_cols = [col for col in weather_cols if col in self.weather_data.columns]
        self.weather_data = self.weather_data[available_cols]
        
        # Rename columns to match LoadMeteoTXT format
        column_mapping = {
            'DryBulb': 'T',
            'DewPoint': 'Td', 
            'RHum': 'hr',
            'Pressure': 'psta',
            'GHI': 'rf1e'
        }
        
        self.weather_data = self.weather_data.rename(columns=column_mapping)
        
    
    def Donnees_Meteo(self):
        """Clean and process weather data (same as LoadMeteoTXT)"""
        # Convert to float
        self.weather_data = self.weather_data.astype(float)
        
        # Calculate solar temperature (same as LoadMeteoTXT)
        if 'T' in self.weather_data.columns and 'rf1e' in self.weather_data.columns:
            self.weather_data['Tsolair'] = (
                self.weather_data['T'] + 0.026 * self.weather_data['rf1e']
            )
        
        # Rename columns for consistency
        if 'Td' in self.weather_data.columns:
            self.weather_data = self.weather_data.rename(columns={'T': 'T', 'Td': 'Td'})
        else:
            self.weather_data = self.weather_data.rename(columns={'T': 'T'})
    
    # def convertHN(self):
    #     """Convert to normal hours (same as LoadMeteoTXT)"""
    #     index = self.weather_data.index
    #     date_debut = index[0].to_pydatetime() - self.local_tz.localize(index[0].to_pydatetime()).dst()
    #     date_fin = index[-1].to_pydatetime() - self.local_tz.localize(index[-1].to_pydatetime()).dst()
    #     normal_index = pd.date_range(date_debut, date_fin, freq='1h')
        
    #     # Ensure same length
    #     if len(normal_index) != len(self.weather_data):
    #         normal_index = pd.date_range(date_debut, periods=len(self.weather_data), freq='1h')
        
    #     self.weather_data.index = normal_index
    #     self.weather_data.index.name = 'HeureNormale'
    
    def temperatureSol(self):
        """Calculate soil temperature (same as LoadMeteoTXT)"""
        tmean = 7.2
        tamp = 20
        tshift = 30
        ksoil = 5.4
        rhosoil = 2400
        cpsoil = 0.84
        rhocp = rhosoil * cpsoil
        z = 1.5
        
        alpha = ksoil / rhocp * 24
        
        tyear = [
            (np.minimum(365, idx.timetuple().tm_yday) - 1 + 
             (idx.timetuple().tm_hour + idx.timetuple().tm_min / 60 + 
              idx.timetuple().tm_sec / 3600) / 24)
            for idx in self.weather_data.index
        ]
        
        a = z * ((math.pi / 365 / alpha) ** 0.5)
        b = z / 2.0 * ((365 / math.pi / alpha) ** 0.5)
        c = [(day - tshift - b) for day in tyear]
        
        Tsol = [tmean - tamp * math.exp(-a) * math.cos(2 * math.pi / 365 * cc) for cc in c]
        
        self.weather_data['Tgrnd'] = Tsol
    
    def changeTimestep(self):
        """Resample to desired timestep (same as LoadMeteoTXT)"""
        self.weather_data = self.weather_data.resample(self.TimeStep).mean()
        self.weather_data = self.weather_data.interpolate(method='slinear')
    
    # def changeTime(self):
    #     """Filter by date range (same as LoadMeteoTXT)"""
    #     Filtre = (self.weather_data.index >= self.DateDebut) & (self.weather_data.index <= self.DateFin)
    #     self.weather_data = self.weather_data[Filtre]
    
    def recolumn(self):
        """Rename columns to standard format (same as LoadMeteoTXT)"""
        raw_columns = ['T', 'Td', 'hr', 'psta', 'rf1e']
        new_columns = ['DryBulb', 'DewPoint', 'RHum', 'Pressure', 'GHI']
        
        mapping = dict(zip(raw_columns, new_columns))
        self.weather_data = self.weather_data.rename(columns=mapping)
    
    def StoreData(self):
        """Store data in Data objects (same as LoadMeteoTXT)"""
        self.Donnees_Meteo = Grp_data()
        
        data_mapping = {
            'DryBulb': 'DryBulb',
            'DewPoint': 'DewPoint', 
            'RHum': 'RHum',
            'Pressure': 'Pressure',
            'GHI': 'GHI',
            'Tgrnd': 'Tgrnd'
        }
        
        for col_name, data_name in data_mapping.items():
            if col_name in self.weather_data.columns:
                data_obj = Data(
                    data_name, '-', 0,
                    list(self.weather_data.index),
                    list(self.weather_data[col_name])
                )
                self.Donnees_Meteo.add(data_name, data_obj)
    
    def CalculMeteo(self):
        """Main calculation method (same interface as LoadMeteoTXT)"""
        self.loadFile()
        self.Donnees_Meteo()
        #self.convertHN()
        
        # if self.DateDebut is not None:
        #     self.changeTime()
        
        self.changeTimestep()
        self.recolumn()
        self.temperatureSol()
        self.StoreData()