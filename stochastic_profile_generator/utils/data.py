# -*- coding: utf-8 -*-
"""
Created on Tue Nov 12 08:37:11 2019

@author: Brice Le Lostec
"""
import pandas as pd


class Data(object):
    """
    Class to store and manage experimental or simulated time series data.
    Attributes:
        name (str): Name of the data (e.g., 'Temperature').
        unit (str): Unit of the data (e.g., 'C', 'kWh').
        dt (float/int): Time step or interval (not used directly in methods).
        time (list): List of timestamps corresponding to the data points.
        data (list): List of data values.
    """


    def __init__(self, name, unit, dt, time, data):
        """
        Initialize a Data object.
        Args:
            name (str): Name of the data.
            unit (str): Unit of the data.
            dt (float/int): Time step or interval.
            time (list or iterable): Timestamps for the data points.
            data (list or iterable): Data values.
        """
        self.name = name
        self.unit = unit
        self.dt = dt
        # Ensure data is a list
        if isinstance(data, list):
            self.data = data
        else:
            self.data = list(data)
        # Ensure time is a list
        if isinstance(time, list):
            self.time = time
        else:
            self.time = list(time)



    def interpol_old(self, newtime):
        """
        Interpolate data to new timestamps using pandas reindex and interpolate.
        Args:
            newtime (list): List of new timestamps to interpolate to.
        Returns:
            list: Interpolated data values at newtime.
        """
        # Create DataFrame with current data and time
        data = pd.DataFrame(self.data, index=pd.to_datetime(self.time))
        # Reindex to newtime and interpolate missing values
        df_reindexed = data.reindex(newtime).interpolate()
        # Return interpolated values as a list
        return list(df_reindexed[list(df_reindexed)][0])
    

    def interpol(self, newtime):
        """
        Interpolate and resample data to new timestamps.
        Args:
            newtime (list): List of new timestamps (must be regularly spaced).
        Returns:
            list: Interpolated and resampled data values at newtime.
        """
        DateDebut = newtime[0]
        DateFin = newtime[-1]
        TimeStep = newtime[1] - newtime[0]  # Assumes newtime is sorted and regular

        # Create DataFrame with current data and time
        data = pd.DataFrame(self.data, index=pd.to_datetime(self.time))
        # Resample to new timestep and interpolate
        data = data.resample(TimeStep).interpolate()
        # Select data within the new time range
        return data.loc[(data.index >= DateDebut) & (data.index <= DateFin)][0].tolist()



class Grp_data(object):
    """
    Dictionary-like container for multiple Data objects.
    Allows adding and removing Data objects by name.
    """

    def __init__(self):
        """
        Initialize an empty group of Data objects.
        """
        self.Grp_data = {}

    def add(self, name, data_cls):
        """
        Add a Data object to the group.
        Args:
            name (str): Key name for the Data object.
            data_cls (Data): Data object to add.
        """
        self.Grp_data[name] = data_cls

    def remove(self, name):
        """
        Remove a Data object from the group by name.
        Args:
            name (str): Key name of the Data object to remove.
        """
        if name in self.Grp_data.keys():
            del self.Grp_data[name]
