# Import necessary libraries
import pandas as pd
import numpy as np
from warnings import simplefilter
simplefilter(action="ignore", category=pd.errors.PerformanceWarning)

import logging
logger = logging.getLogger(__name__)

# Function to preprocess the data
def preprocess_data_types(data: pd.DataFrame, args_constraints: dict):
	"""
	Preprocess the input data based on the provided argument constraints 
	so that each column gets the right data type.

	Args:
		data (pd.DataFrame): The input data to preprocess.
		args_constraints (dict): The argument constraints from the HPXML schema.
	
	Returns:
		data: The preprocessed data as a dataframe.
		list_columns_hpxml: The list of columns that are part of the HPXML schema.
	"""
	# Convert each column in the dataframe data to the appropriate data type
	dict_data_types = {
		'Boolean': bool,
		'Integer': int,
		'Choice': str,
		'Double': float,
		'String': str
		}
	list_columns_hpxml = []
	for column in data.columns:
		if column in args_constraints.keys():
			col_type = args_constraints[column]['Type']
			if col_type == 'String' or col_type == 'Choice':
				# Preserve NaN for string-like columns instead of converting to literal "nan"
				data[column] = data[column].where(data[column].isna(), data[column].astype(str))
			else:
				data[column] = data[column].astype(dict_data_types[col_type])
			list_columns_hpxml.append(column)

	# Add building_id column to the data DataFrame
	data['building_id'] = np.arange(1, len(data) + 1)

	# Add other missing hpxml columns with default None values
	list_missing_hpxml_columns = [col for col in args_constraints.keys() if col not in list_columns_hpxml]
	data[list_missing_hpxml_columns] = None

	# Return the preprocessed data
	return data, list_columns_hpxml

# Function to preprocess the data
def preprocess_data_to_dict(data: pd.DataFrame, args_constraints: dict, list_columns_hpxml: list):
	"""
	Preprocess the input data based on the provided argument constraints and 
	generate a list of dictionaries, each dictionary representing a building
	using attributes from the HPXML schema.

	Args:
		data (pd.DataFrame): The input data to preprocess.
		args_constraints (dict): The argument constraints from the HPXML schema.
		list_columns_hpxml (list): The list of columns from the input data that 
			are part of the HPXML schema.
	
	Returns:
		data_dict: The preprocessed data as a list of dictionaries.
	"""
	# Check if the input data is empty
	if data is None or data.empty:
		return None

	# Transform the data DataFrame to a list of dictionaries
	data_dict = data.to_dict(orient='records')
	new_data_dict = []

	# Check the attributes for each building and remove invalid ones
	list_attributes_to_check = [i for i in list_columns_hpxml if args_constraints[i]['Type'] == 'Choice'] 
	for idata in data_dict:
		new_idata = {}
		new_idata['hpxml_args'] = {}
		new_idata['non_hpxml_args'] = {}
		for attribute in idata.keys():
			if attribute in list_attributes_to_check:
				if idata[attribute] not in args_constraints[attribute]['Choices']:
					logger.warning(f"Attribute '{attribute}' with value '{idata[attribute]}' is not valid. "
						f"Valid values are: {args_constraints[attribute]['Choices']}.")
					# The attribute is not added in the updated dictionary (new_idata) if it is not valid
				else:
					new_idata['hpxml_args'][attribute] = idata[attribute]
			elif ((pd.isnull(idata[attribute]))):
				logger.warning(f"Attribute '{attribute}' with value '{idata[attribute]}' is not valid. ")
				# The attribute is not added in the updated dictionary (new_idata) if it is not valid
			elif attribute in args_constraints.keys():
				new_idata['hpxml_args'][attribute] = idata[attribute]
			else:
				new_idata['non_hpxml_args'][attribute] = idata[attribute]
		new_idata['non_hpxml_args']['weather_station_epw'] = idata['weather_station_epw_filepath']
		new_data_dict.append(new_idata)

	# Return the preprocessed data
	return new_data_dict