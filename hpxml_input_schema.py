# Import necessary libraries
import xml.etree.ElementTree as ET
import pandas as pd

# Function to parse XML file
def parse_xml_file(file_path):
	"""
	Parse the XML file and return the root element.
	
	Args:
		file_path (str): Path to the XML file.
	
	Returns:
		Element: Root element of the parsed XML file.
	"""
	try:
		tree = ET.parse(file_path)
		root = tree.getroot()
		return root
	except ET.ParseError as e:
		print(f"Error parsing XML file: {e}")
		return None
	
# Function to extract arguments from the XML file
def extract_arguments_from_xml(file_path):
	"""
	Extract arguments from the XML file and return them as a list of dictionaries.
	
	Args:
		file_path (str): Path to the XML file.
	
	Returns:
		List[Dict]: List of dictionaries containing argument details.
	"""
	root = parse_xml_file(file_path)
	if root is None:
		return []

	arguments = root.findall('.//argument')
	ListDictArgs = []
	for argument in arguments:
		argdict = {}
		if argument.find('name') is not None:
			argdict['Name'] = argument.find('name').text
		if argument.find('display_name') is not None:
			argdict['Display Name'] = argument.find('display_name').text
		if argument.find('description') is not None:
			argdict['Description'] = argument.find('description').text
		if argument.find('type') is not None:
			argdict['Type'] = argument.find('type').text
		if argument.find('units') is not None:
			argdict['Units'] = argument.find('units').text
		if argument.find('default_value') is not None:
			argdict['Default Value'] = argument.find('default_value').text
		if argument.find('choices') is not None:
			choices = argument.find('choices').findall('.//choice')
			listChoices = [choice.find('value').text for choice in choices]
			argdict['Choices'] = listChoices
		if argument.find('required') is not None:
			argdict['Required'] = argument.find('required').text
		ListDictArgs.append(argdict)
	
	df = pd.DataFrame(ListDictArgs)

	# Convert the 'Required' column to boolean
	df['Required'] = df['Required'].apply(lambda x: True if x.lower() == 'true' else False)

	# Convert the DataFrame df to a dictionary
	# with 'Name' as keys and the rest of the columns as values
	listNames = df['Name'].tolist()
	df_2 = df[['Type','Required','Choices','Default Value']].to_dict(orient='records')
	args_constraints = dict(zip(listNames, df_2))

	# Modify the dictionary args_constraints so that it gets the correct data types
	data_types = {
		'Boolean': bool,
		'Integer': int,
		'Choice': str,
		'Double': float,
		'String': str
		}
	for i in args_constraints.keys():
		if pd.isna(args_constraints[i]['Default Value']) == False:
			args_constraints[i]['Default Value'] = data_types[args_constraints[i]['Type']](args_constraints[i]['Default Value'])

	return args_constraints