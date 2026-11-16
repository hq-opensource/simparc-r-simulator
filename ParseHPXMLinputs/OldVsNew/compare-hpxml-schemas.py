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

# NORMALIZE LIST-LIKE CONTENT TO A HASHABLE FORM BEFORE MERGE

def make_hashable(value):
	if isinstance(value, list):
		return tuple(value)
	return value

# PARSE CURRENT XML FILE
current = parse_xml_file(os.path.dirname(os.path.abspath(__file__))+'/schemas-2-be-compared/measure_current.xml')
arguments = current.findall('.//argument')
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

df_current = pd.DataFrame(ListDictArgs)
df_current.to_csv(os.path.dirname(os.path.abspath(__file__))+'/HPXMLinputs_current.csv', 
                  index=False, sep=',')

# PARSE NEW XML FILE
new = parse_xml_file(os.path.dirname(os.path.abspath(__file__))+'/schemas-2-be-compared/measure_new.xml')
arguments = new.findall('.//argument')
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

df_new = pd.DataFrame(ListDictArgs)
df_new.to_csv(os.path.dirname(os.path.abspath(__file__))+'/HPXMLinputs_new.csv', 
                  index=False, sep=',')

# COMPARE CURRENT AND NEW DATAFRAMES
# Normalize list-like values so pandas can hash the join keys.
df_current_for_merge = df_current.copy()
df_new_for_merge = df_new.copy()
for df in (df_current_for_merge, df_new_for_merge):
	if 'Choices' in df.columns:
		df['Choices'] = df['Choices'].map(make_hashable)

df_strictly_similar = pd.merge(df_current_for_merge, df_new_for_merge, how='inner',
                               on=['Name', 'Display Name', 'Description', 'Type', 
                                   'Required', 'Choices', 'Units', 'Default Value'])

df_same_name_but_different = pd.merge(df_current_for_merge, df_new_for_merge, how='inner',
                                      on=['Name'])
df_same_name_but_different = df_same_name_but_different[~df_same_name_but_different['Name'].isin(df_strictly_similar['Name'])]

df1 = df_strictly_similar.copy()
df1['Source'] = 'Both'
df2 = df_current_for_merge[df_current_for_merge['Name'].isin(df_same_name_but_different['Name'])].copy()
df2['Source'] = 'Current - same name but different'
df3 = df_new_for_merge[df_new_for_merge['Name'].isin(df_same_name_but_different['Name'])].copy()
df3['Source'] = 'New - same name but different'
df4 = df_current_for_merge[~df_current_for_merge['Name'].isin(df_same_name_but_different['Name']) & 
                           ~df_current_for_merge['Name'].isin(df_strictly_similar['Name'])].copy()
df4['Source'] = 'Only Current'
df5 = df_new_for_merge[~df_new_for_merge['Name'].isin(df_same_name_but_different['Name']) & 
                       ~df_new_for_merge['Name'].isin(df_strictly_similar['Name'])].copy()
df5['Source'] = 'Only New'
df_final = pd.concat([df1, df2, df3, df4, df5], ignore_index=True)
df_final.to_csv(os.path.dirname(os.path.abspath(__file__))+'/HPXMLinputs_comparison.csv', index=False, sep=',')
