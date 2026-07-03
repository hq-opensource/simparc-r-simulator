################################################################################
# PARSE HPXML INPUTS
################################################################################

# LIBRARIES
import xml.etree.ElementTree as ET
import pandas as pd
import os

# PARSE XML FILE FUNCTION
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

# PARSE XML FILE
test = parse_xml_file(os.path.dirname(os.path.abspath(__file__))+'/measure.xml')
arguments = test.findall('.//argument')
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
		listChoices = []
		for choice in choices:
			listChoices.append(choice.find('value').text)
		argdict['Choices'] = listChoices
	if argument.find('required') is not None:
		argdict['Required'] = argument.find('required').text
	ListDictArgs.append(argdict)

df = pd.DataFrame(ListDictArgs)
df.to_csv('HPXMLinputs.csv', index=False, sep=',')
