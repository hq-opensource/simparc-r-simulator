## Liste changements effectué pour migration

## Globaux

- Passage de openstudio 3.9.0 vers 3.11.0
- Remplacement des scripts du dossier measure par le submodule OpenStudio-HPXML v1.12.0 ( implique HPXML v5.0-rc1)

## Code

### building.py

- ajustement pour utiliser le submodule OpenStudio-HPXML


### utils.py

- ajustement pour utiliser le submodule OpenStudio-HPXML
- les helpers qui assemblent plusieurs colonnes legacy ou font du matching TSV restent dans `utils.py`; `migration_helper.py` est rÃ©servÃ© aux formatters scalaires simples.


## Modification de  paramètres

| Ancien                     | Nouveau             | Fichiers modifiés                           | Commentaire                                                   |
|----------------------------|----------------------|----------------------------------------------|---------------------------------------------------------------|
| weather_station_epw_filepath | location_epw_path   | building.py; local.py; preprocessing.py      |                                                               |
| SIMULATION_TIMESTEP        | SIMULATION_TIMESTEP  | local.py                                     | Le nom n'a pas changé, seulement le type (string maintenant) |


## Outil de migration

Le script migrate_csv.py vise à  convertir un fichier csv d'entrée concu pour openstudio 3.9.0 afin de pouvoir l'utiliser en entreée de openstudio 3.11. La liste des modifcations faites par l'outils se trouve ci-bas

### État courant de la migration

Bloc dÃ©jÃ Â  validé, documenté dans `migration.md` et retirÃ© de `suivi.md`:
- `clothes_dryer_present` / `clothes_dryer_fuel_type` / `clothes_dryer_efficiency_type` / `clothes_dryer_efficiency` / `clothes_dryer_vented_flow_rate` / `clothes_dryer_usage_multiplier` / `clothes_dryer_location` / `clothes_washer_present` / `clothes_washer_efficiency_type` / `clothes_washer_efficiency` / `clothes_washer_rated_annual_kwh` / `clothes_washer_label_electric_rate` / `clothes_washer_label_gas_rate` / `clothes_washer_label_annual_gas_cost` / `clothes_washer_label_usage` / `clothes_washer_capacity` / `clothes_washer_usage_multiplier` / `clothes_washer_location` / `dishwasher_present` / `dishwasher_efficiency_type` / `dishwasher_efficiency` / `dishwasher_label_electric_rate` / `dishwasher_label_gas_rate` / `dishwasher_label_annual_gas_cost` / `dishwasher_label_usage` / `dishwasher_place_setting_capacity` / `dishwasher_usage_multiplier` / `dishwasher_location` / `refrigerator_present` / `refrigerator_rated_annual_kwh` / `refrigerator_usage_multiplier` / `refrigerator_location` / `extra_refrigerator_present` / `extra_refrigerator_rated_annual_kwh` / `extra_refrigerator_usage_multiplier` / `extra_refrigerator_location` / `dehumidifier_type` / `dehumidifier_efficiency_type` / `dehumidifier_efficiency` / `dehumidifier_capacity` / `dehumidifier_rh_setpoint` / `dehumidifier_fraction_dehumidification_load_served`
- `overhangs_*` vers `enclosure_overhangs`
- `ducts_*` vers `hvac_ducts`
- `heat_pump_*` vers les options v1.12
- `pool_*` vers `misc_pool`
- `permanent_spa_*` vers `misc_permanent_spa`

Bloc restant à  reprendre en priorité:
- enveloppe, ECS, éclairage, appareils, PV, barrière radiante, toiture, chaudière, humidification/déshumidification, et les colonnes encore non traitées dans `Instruction.md`

Règle de reprise:
- Si une colonne legacy est déjà  prise en charge par `migrate_csv.py`, elle doit àªtre documentée ici puis déplacée dans `suivi.md` comme réglée.
- Si une colonne n'est pas encore prise en charge, elle reste dans la liste à  migrer de `Instruction.md` et dans la section à  réviser de `suivi.md`.

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
  - Lorsqu'il existe plusieurs options valides pour un màªme type, geometry_foundation_height_above_grade est utilisé pour choisir l'option la plus proche.
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
  - Màªme logique de correspondance exacte/fallback que pour `misc_pool`, avec les options de `OpenStudio-HPXML/BuildResidentialHPXML/resources/options/misc_permanent_spa.tsv`.
- Après migration, les colonnes legacy pool/spa sont supprimées du CSV de sortie.
- Migration des paramÃ¨tres legacy ECS vers `dhw_water_heater` et `dhw_water_heater_location`:
  - Colonnes converties: `water_heater_fuel_type`, `water_heater_efficiency_type`, `water_heater_efficiency`, `water_heater_recovery_efficiency`, `water_heater_standby_loss`, `water_heater_jacket_rvalue`, `water_heater_setpoint_temperature`, `water_heater_type`, `water_heater_location`.
  - `water_heater_location` est reclassÃ© vers les emplacements canoniques v1.12; les valeurs non reconnues retombent sur `Default`.
  - Les colonnes legacy non reprises sont supprimÃ©es aprÃ¨s migration.
  - La correspondance de `dhw_water_heater` privilÃ©gie le type, le combustible et lâ€™efficacitÃ©, puis choisit lâ€™option la plus proche dans `dhw_water_heater.tsv`.
- Migration de `floor_type`, `slab_perimeter_insulation_r` et `slab_under_insulation_r` vers `enclosure_slab`:
  - Les cas sans isolation deviennent `Uninsulated`.
  - Les cas Ã  isolation unique sont convertis vers les options `Under Slab, 2ft, R-x` ou `Perimeter, 2ft, R-x` selon la colonne renseignÃ©e.
  - Quand les deux isolations sont prÃ©sentes, la migration retient une reprÃ©sentation cohÃ©rente dans `enclosure_slab` et signale l'approximation au besoin.
  - `floor_type` nâ€™a plus dâ€™Ã©quivalent direct dans le measure v1.12 et est supprimÃ© aprÃ¨s migration.
- `geometry_building_num_units` est conservé comme champ de migration et transmis au backend HPXML, qui l'écrit vers `NumberofUnitsInBuilding`.
- `year_built` est renommé en `building_year_built`.
- `geometry_unit_cfa` est renommé en `geometry_unit_conditioned_floor_area`.
- `geometry_roof_type` est absorbé par la logique de `geometry_attic_type` et `geometry_roof_pitch` dans le measure v1.12.
- Migration de `hvac_ducts` :
  - Les colonnes legacy `ducts_leakage_units`, `ducts_supply_leakage_to_outside_value`, `ducts_supply_insulation_r`, `ducts_return_leakage_to_outside_value` et `ducts_return_insulation_r` sont consolidées en un seul paramètre option-string `hvac_ducts`.
  - La migration accepte d'abord une valeur déjà  valide de `hvac_ducts` (Option Name issue de `hvac_ducts.tsv`) et la conserve telle quelle.
  - Les cas sans conduits sont détectés explicitement via `HVAC Has Ducts` ou la valeur legacy `No`/`None`/`Aucun`, et alors la valeur finale devient `"None"`.
  - Les unités de fuite sont normalisées (`Percent`, `CFM`, `ACH`, etc.) avant la comparaison, et les valeurs de fuite en pourcentage sont converties au format attendu par les options canonique.
  - Quand une seule des deux valeurs de fuite (supply/return) est fournie, la valeur manquante est répliquée pour conserver une estimation cohérente du total.
  - Le total de fuite (supply + return) ainsi que les valeurs d'isolation R sont comparés aux options de `hvac_ducts.tsv`, avec un matching "nearest match" parmi les options valides. Si les options détaillées incluent une fraction de fuite d'alimentation, la fraction calculée est prise en compte pour choisir l'option la plus proche.
  - Les colonnes legacy sont supprimées automatiquement après migration afin de ne laisser que le nouveau paramètre `hvac_ducts` dans le CSV final.

  - Migration de `foundation_wall_type` vers `enclosure_foundation_wall`.
    - Les colonnes legacy `foundation_wall_type`, `foundation_wall_insulation_r`, `foundation_wall_insulation_location` et `foundation_wall_insulation_distance_to_top` sont combinÃ©es pour retrouver l'option canonique.
    - Lors d'un rapprochement approximatif, le log indique explicitement l'option choisie et la valeur associÃ©e issue du TSV.


