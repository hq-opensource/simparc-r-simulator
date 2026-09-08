## Liste changements effectué pour migration

## Globaux

- Passage de openstudio 3.9.0 vers 3.11.0
- Remplacement des scripts du dossier measure par le submodule OpenStudio-HPXML v1.12.0 ( implique HPXML v5.0-rc1)

## Code

### building.py

- ajustement pour utiliser le submodule OpenStudio-HPXML


### utils.py

- ajustement pour utiliser le submodule OpenStudio-HPXML


## Modification de  paramètres

| Ancien                     | Nouveau             | Fichiers modifiés                           | Commentaire                                                   |
|----------------------------|----------------------|----------------------------------------------|---------------------------------------------------------------|
| weather_station_epw_filepath | location_epw_path   | building.py; local.py; preprocessing.py      |                                                               |
| SIMULATION_TIMESTEP        | SIMULATION_TIMESTEP  | local.py                                     | Le nom n’a pas changé, seulement le type (string maintenant) |


## Outil de migration

Le script migrate_csv.py vise à convertir un fichier csv d'entrée concu pour openstudio 3.9.0 afin de pouvoir l'utiliser en entreée de openstudio 3.11. La liste des modifcations faites par l'outils se trouve ci-bas

- Remplacement de 'none' par 'not present' pour un ensemble de colonnes. Voir la méthode update_column_values_v110_to_v112().
- Remplacement des paramètres air_leakage_value, air_leakage_units et air_leakage_house_pressure par un seul paramètre enclosure_air_leakage.
  - Les valeurs admissibles proviennent de OpenStudio-HPXML/BuildResidentialHPXML/resources/options/enclosure_air_leakage.tsv.
  - Le script normalise les formats legacy (espaces, casse, formats ACH/CFM/nACH) et mappe ensuite vers les options canoniques.
  - *WARNING* ce remplacement peut introduire une perte de précision: une valeur continue est convertie vers une liste d'options prédéfinies. La règle appliquée est la valeur disponible la plus proche.
- Migration de geometry_unit_type vers les Option Name de OpenStudio-HPXML/BuildResidentialHPXML/resources/options/geometry_unit_type.tsv.
  - La migration utilise geometry_unit_num_floors_above_grade pour sélectionner l'option finale (ex.: Apartment Unit, 1 Story).
  - Les valeurs legacy sont normalisées (espaces/tirets/casse) avant correspondance.
- Migration de geometry_attic_type vers les Option Name de OpenStudio-HPXML/BuildResidentialHPXML/resources/options/geometry_attic_type.tsv.
  - La migration combine geometry_attic_type et geometry_roof_type pour trouver l'option canonique (ex.: Attic, Vented, Gable).
  - En fallback, si le type de toit est absent/non reconnu, une option par défaut cohérente est choisie (préférence gable quand applicable).
- Migration de geometry_foundation_type vers les Option Name de OpenStudio-HPXML/BuildResidentialHPXML/resources/options/geometry_foundation_type.tsv.
  - Les valeurs legacy sont normalisées (espaces/tirets/casse) avant correspondance.
  - Lorsqu'il existe plusieurs options valides pour un même type, geometry_foundation_height_above_grade est utilisé pour choisir l'option la plus proche.
- Migration vers enclosure_overhang qui remplce overhang_front,  overhangs_bask, overhangs_right, ov erhangs_left (* depth, top_to_window, bottom_to_window)
  - perte de granularique, les valeur bottom et top sont regroupés en 1 valeur
  - perte de précision, les valeur 'double' sont remplacé par des olptions prédéfinies
- Migration des paramètres legacy de piscine vers `misc_pool`:
  - Colonnes converties: `pool_present`, `pool_pump_annual_kwh`, `pool_pump_usage_multiplier`, `pool_heater_type`, `pool_heater_annual_kwh`, `pool_heater_annual_therm`, `pool_heater_usage_multiplier`.
  - Si une correspondance exacte existe dans `OpenStudio-HPXML/BuildResidentialHPXML/resources/options/misc_pool.tsv`, elle est utilisée.
  - Sinon, une option de type "Usage" est reconstruite en rapprochant le multiplicateur vers les valeurs supportées (25/50/75/100/150/200/400%).
  - Les cas "Detailed Example" sont utilisés lorsque les valeurs annuelles (kWh/therm) correspondent.
- Migration des paramètres legacy de spa vers `misc_permanent_spa`:
  - Colonnes converties: `permanent_spa_present`, `permanent_spa_pump_annual_kwh`, `permanent_spa_pump_usage_multiplier`, `permanent_spa_heater_type`, `permanent_spa_heater_annual_kwh`, `permanent_spa_heater_annual_therm`, `permanent_spa_heater_usage_multiplier`.
  - Même logique de correspondance exacte/fallback que pour `misc_pool`, avec les options de `OpenStudio-HPXML/BuildResidentialHPXML/resources/options/misc_permanent_spa.tsv`.
- Après migration, les colonnes legacy pool/spa sont supprimées du CSV de sortie.
- migration de 
  - `ducts_leakage_units`, `ducts_supply_leakage_to_outside_value`,  `ducts_return_insulation_r`,  `ducts_return_leakage_to_outside_value` 
- vers `hvac_ducts`


