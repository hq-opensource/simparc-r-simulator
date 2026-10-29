# Instructions

Documenter les colonnes migrÃ©es. Indiquer l'ancien nom, le changement appliquÃ© (renommage, fusion, changement de type, suppression, autre), l'impact sur les rÃ©sultats, le nouveau nom si pertinent, la fonction avant, la nouvelle fonction si pertinent, et la justification de la modification.

# DÃ©tail

## PremiÃ¨res colonnes migrÃ©es

La liste ci-dessous est triÃ©e par ordre alphabÃ©tique du nom de colonne d'origine.

- `air_leakage_value` / `air_leakage_units` / `air_leakage_house_pressure`
	- Changement appliquÃ© : fusion + renommage
	- Impact rÃ©sultats : aucun pour les valeurs reconnues; lÃ©gÃ¨re approximation possible lors du rapprochement vers l'option canonique
	- Nouveau nom si pertinent : `enclosure_air_leakage`
	- Fonction avant : fuite d'air dÃ©crite par valeur, unitÃ© et pression de test
	- Nouvelle fonction : `update_air_leakage_v110_to_v112()`
	- Justification : la v1.12 encode la fuite d'air comme option-string canonique; la migration reconstruit la valeur legacy puis la rapproche de l'option la plus proche dans le TSV.

- `geometry_attic_type` / `geometry_roof_type`
	- Changement appliquÃ© : fusion + renommage
	- Impact rÃ©sultats : aucun
	- Nouveau nom si pertinent : `geometry_attic_type`
	- Fonction avant : type d'attic combinÃ© au type de toit
	- Nouvelle fonction : `update_geometry_attic_v110_to_v112()`
	- Justification : la v1.12 porte la logique de toit dans les noms d'options d'attic; `geometry_roof_type` est absorbÃ© pour produire l'option finale.

- `geometry_average_ceiling_height`
	- Changement appliquÃ© : changement de type + renommage
	- Impact rÃ©sultats : perte de prÃ©cision mineure
	- Nouveau nom si pertinent : `geometry_ceiling_height`
	- Fonction avant : valeur libre en pieds (`Double`)
	- Nouvelle fonction : `update_geometry_average_ceiling_height_v110_to_v112()`
	- Justification : la v1.12 remplace le champ libre par une liste dâ€™options prÃ©dÃ©finies (`Choice`) afin dâ€™aligner lâ€™interface avec les options du measure.

- `geometry_building_num_units`
	- Changement appliquÃ© : autre
	- Impact rÃ©sultats : aucun
	- Nouveau nom si pertinent : `BuildingConstruction/NumberofUnitsInBuilding` cÃ´tÃ© HPXML, mais pas comme argument CSV direct
	- Fonction avant : nombre dâ€™unitÃ©s fourni explicitement
	- Nouvelle fonction : `update_geometry_building_num_units_v110_to_v112()`
	- Justification : le measure ne lâ€™expose plus comme argument direct, mais le backend HPXML le consomme encore et lâ€™Ã©crit vers `NumberofUnitsInBuilding`.

- `geometry_foundation_height` / `geometry_foundation_height_above_grade` / `geometry_rim_joist_height` / `geometry_foundation_type`
	- Changement appliquÃ© : fusion + renommage
	- Impact rÃ©sultats : aucun pour les cas standard; les hauteurs servent Ã  sÃ©lectionner la variante de fondation appropriÃ©e
	- Nouveau nom si pertinent : `geometry_foundation_type`
	- Fonction avant : type de fondation et hauteurs associÃ©es
	- Nouvelle fonction : `update_geometry_foundation_v110_to_v112()`
	- Justification : la v1.12 encode les variantes de fondation dans les noms d'options; les hauteurs legacy servent Ã  choisir la bonne option plutÃ´t qu'Ã  rester en colonnes sÃ©parÃ©es.

- `foundation_wall_type` / `foundation_wall_insulation_r` / `foundation_wall_insulation_location` / `foundation_wall_insulation_distance_to_top`
	- Changement appliquÃ© : fusion + renommage
	- Impact rÃ©sultats : aucun pour les correspondances exactes; rapprochement possible vers lâ€™option la plus proche sinon
	- Nouveau nom si pertinent : `enclosure_foundation_wall`
	- Fonction avant : type de mur de fondation et champs dâ€™isolation dÃ©taillÃ©s
	- Nouvelle fonction : `update_enclosure_foundation_wall_v110_to_v112()`
	- Justification : la v1.12 concentre le mur de fondation dans un choix canonique; la migration combine le type, la valeur R, la position de lâ€™isolant et la distance au sommet pour retrouver lâ€™option la plus proche dans `enclosure_foundation_wall.tsv`.

- `floor_type` / `slab_perimeter_insulation_r` / `slab_under_insulation_r`
	- Changement appliquÃ© : suppression + fusion partielle vers `enclosure_slab`
	- Impact rÃ©sultats : aucun pour les cas simples; approximation possible lorsque les isolations legacy sont ambiguÃ«s ou simultanÃ©es
	- Nouveau nom si pertinent : `enclosure_slab`
	- Fonction avant : type de plancher legacy plus deux R-values de dalle sÃ©parÃ©es
	- Nouvelle fonction : `update_enclosure_slab_v110_to_v112()`
	- Justification : la v1.12 reprÃ©sente la dalle comme option-string canonique. La migration reconstruit lâ€™option Ã  partir des R-values legacy, choisit une reprÃ©sentation cohÃ©rente quand les deux isolations sont prÃ©sentes, et supprime ensuite les colonnes legacy. `floor_type` nâ€™a plus dâ€™Ã©quivalent direct dans le measure v1.12 et est absorbÃ© par le backend.

- `wall_type` / `wall_assembly_r`
	- Changement appliquÃ© : fusion + renommage
	- Impact rÃ©sultats : aucun pour les correspondances exactes; rapprochement possible vers lâ€™option la plus proche sinon. Valider si l'impact est majeur.
	- Nouveau nom si pertinent : `enclosure_wall`
	- Fonction avant : type de mur et R-value dâ€™assemblage sÃ©parÃ©s
	- Nouvelle fonction : `update_enclosure_wall_v110_to_v112()`
	- Justification : la v1.12 encode le type de mur et son isolation dâ€™assemblage dans un seul choix; la migration choisit lâ€™option la plus proche dans `enclosure_wall.tsv`.

- `ceiling_assembly_r`
	- Changement appliquÃ© : renommage
	- Impact rÃ©sultats : aucun pour les correspondances exactes; rapprochement possible vers lâ€™option la plus proche sinon
    Valider si l'impact est majeur.
	- Nouveau nom si pertinent : `enclosure_ceiling`
	- Fonction avant : R-value dâ€™assemblage du plafond
	- Nouvelle fonction : `update_enclosure_ceiling_v110_to_v112()`
	- Justification : la v1.12 attend un choix canonique de plafond; la migration rapproche le R-value legacy vers `enclosure_ceiling.tsv`.

- `floor_over_foundation_assembly_r`
	- Changement appliquÃ© : renommage
	- Impact rÃ©sultats : aucun pour les correspondances exactes; rapprochement possible vers lâ€™option la plus proche sinon
    Valider si l'impact est majeur.
	- Nouveau nom si pertinent : `enclosure_floor_over_foundation`
	- Fonction avant : R-value dâ€™assemblage du plancher sur fondation
	- Nouvelle fonction : `update_enclosure_floor_over_foundation_v110_to_v112()`
	- Justification : la v1.12 encode ce plancher dans un choix canonique; la migration rapproche le R-value legacy vers `enclosure_floor_over_foundation.tsv`.

- `floor_over_garage_assembly_r`
	- Changement appliquÃ© : renommage
	- Impact rÃ©sultats : aucun pour les correspondances exactes; rapprochement possible vers lâ€™option la plus proche sinon
    Valider si l'impact est majeur.
	- Nouveau nom si pertinent : `enclosure_floor_over_garage`
	- Fonction avant : R-value dâ€™assemblage du plancher sur garage
	- Nouvelle fonction : `update_enclosure_floor_over_garage_v110_to_v112()`
	- Justification : la v1.12 encode ce plancher dans un choix canonique; la migration rapproche le R-value legacy vers `enclosure_floor_over_garage.tsv`.

- `geometry_unit_cfa`
	- Changement appliquÃ© : renommage
	- Impact rÃ©sultats : aucun
	- Nouveau nom si pertinent : `geometry_unit_conditioned_floor_area`
	- Fonction avant : aire conditionnÃ©e du logement
	- Nouvelle fonction : `update_geometry_unit_cfa_v110_to_v112()`
	- Justification : le measure v1.12 utilise `geometry_unit_conditioned_floor_area` pour lâ€™aire de plancher conditionnÃ©e.

- `geometry_unit_num_floors_above_grade` / `geometry_unit_type`
	- Changement appliquÃ© : fusion + renommage
	- Impact rÃ©sultats : aucun
	- Nouveau nom si pertinent : `geometry_unit_type`
	- Fonction avant : type d'unitÃ© et nombre d'Ã©tages au-dessus du sol
	- Nouvelle fonction : `update_geometry_unit_v110_to_v112()`
	- Justification : la v1.12 encode le type d'unitÃ© et le nombre d'Ã©tages dans une seule option; la migration combine les deux colonnes legacy pour retrouver l'option canonique.

- `pool_present` / `pool_pump_annual_kwh` / `pool_pump_usage_multiplier` / `pool_heater_type` / `pool_heater_annual_kwh` / `pool_heater_annual_therm` / `pool_heater_usage_multiplier`
	- Changement appliquÃ© : fusion vers `misc_pool`
	- Impact rÃ©sultats : aucun pour les correspondances exactes; rapprochement possible vers l'option la plus proche sinon
	- Nouveau nom si pertinent : `misc_pool`
	- Fonction avant : prÃ©sence, pompe, chauffage et multiplicateur de la piscine dÃ©crits par plusieurs colonnes legacy
	- Nouvelle fonction : `update_pool_parameters_v110_to_v112()`
	- Justification : la v1.12 concentre les paramÃ¨tres piscine dans une option unique; la migration reconstruit l'option Ã  partir des colonnes legacy et supprime ensuite ces colonnes du CSV.

- `water_heater_fuel_type` / `water_heater_efficiency_type` / `water_heater_efficiency` / `water_heater_recovery_efficiency` / `water_heater_standby_loss` / `water_heater_jacket_rvalue` / `water_heater_setpoint_temperature` / `water_heater_type`
	- Changement appliquÃ© : fusion + renommage + suppression de paramÃ¨tres legacy non repris
	- Impact rÃ©sultats : aucun pour les correspondances exactes; approximation possible pour les combinaisons legacy qui n'ont plus d'Ã©quivalent strict
	- Nouveau nom si pertinent : `dhw_water_heater`
	- Fonction avant : type de chauffe-eau, combustible, efficacitÃ© et paramÃ¨tres annexes legacy
	- Nouvelle fonction : `update_dhw_water_heater_v110_to_v112()`
	- Justification : la v1.12 concentre lâ€™Ã©quipement ECS dans une option canonique; la migration choisit lâ€™option la plus proche dans `dhw_water_heater.tsv` Ã  partir du type, du combustible et de lâ€™efficacitÃ©, puis supprime les colonnes legacy non reprises.

- `water_heater_location`
	- Changement appliquÃ© : renommage
	- Impact rÃ©sultats : aucun
	- Nouveau nom si pertinent : `dhw_water_heater_location`
	- Fonction avant : localisation du chauffe-eau
	- Nouvelle fonction : `update_dhw_water_heater_v110_to_v112()`
	- Justification : la v1.12 garde un argument dÃ©diÃ© Ã  la localisation du chauffe-eau; la migration applique une correspondance directe vers les emplacements canoniques, avec fallback sur `Default`.


- `mech_vent_fan_type` / `mech_vent_flow_rate` / `mech_vent_hours_in_operation` / `mech_vent_recovery_efficiency_type` / `mech_vent_total_recovery_efficiency` / `mech_vent_sensible_recovery_efficiency` / `mech_vent_fan_power` / `mech_vent_num_units_served`
	- Changement appliquÃ© : fusion + renommage + absorption partielle des dÃ©tails legacy non repris
	- Impact rÃ©sultats : aucun pour les correspondances exactes; approximation possible si les rendements legacy ne tombent pas sur une option canonique exacte
	- Nouveau nom si pertinent : `ventilation_mechanical`
	- Fonction avant : ventilation mÃ©canique rÃ©partie sur plusieurs colonnes legacy
	- Nouvelle fonction : `update_ventilation_v110_to_v112()`
	- Justification : la v1.12 regroupe la ventilation mÃ©canique dans une option canonique; la migration remappe le systÃ¨me via le TSV `ventilation_mechanical.tsv`.

- `whole_house_fan_present` / `whole_house_fan_flow_rate` / `whole_house_fan_power`
	- Changement appliquÃ© : fusion + renommage + suppression des dÃ©tails legacy non repris
	- Impact rÃ©sultats : aucun pour les correspondances exactes; approximation possible si le couple dÃ©bit / puissance ne correspond pas exactement Ã  une option canonique
	- Nouveau nom si pertinent : `ventilation_whole_house_fan`
	- Fonction avant : ventilateur global dÃ©crit par prÃ©sence, dÃ©bit et puissance
	- Nouvelle fonction : `update_ventilation_v110_to_v112()`
	- Justification : la v1.12 encode le ventilateur global comme option canonique; la migration rapproche le dÃ©bit et la puissance vers lâ€™option la plus proche dans `ventilation_whole_house_fan.tsv`.

- `kitchen_fans_start_hour`
	- Changement appliquÃ© : absorption par dÃ©faut
	- Impact rÃ©sultats : aucun pour le comportement fonctionnel; la valeur legacy est conservÃ©e dans le journal d'approximation pour traÃ§abilitÃ©
	- Nouveau nom si pertinent : `ventilation_kitchen`
	- Fonction avant : heure de dÃ©marrage du ventilateur de cuisine
	- Nouvelle fonction : `update_ventilation_v110_to_v112()`
	- Justification : la v1.12 nâ€™expose pas de champ Ã©quivalent direct pour cette granularitÃ©; la migration utilise `Default` et logge la valeur legacy.

- `bathroom_fans_start_hour`
	- Changement appliquÃ© : absorption par dÃ©faut
	- Impact rÃ©sultats : aucun pour le comportement fonctionnel; la valeur legacy est conservÃ©e dans le journal d'approximation pour traÃ§abilitÃ©
	- Nouveau nom si pertinent : `ventilation_bathroom`
	- Fonction avant : heure de dÃ©marrage du ventilateur de salle de bains
	- Nouvelle fonction : `update_ventilation_v110_to_v112()`
	- Justification : la v1.12 nâ€™expose pas de champ Ã©quivalent direct pour cette granularitÃ©; la migration utilise `Default` et logge la valeur legacy.

- `window_fraction_operable`
	- Changement appliquÃ© : renommage
	- Impact rÃ©sultats : aucun pour les correspondances exactes; rapprochement possible vers l'option la plus proche sinon
	- Nouveau nom si pertinent : `enclosure_window_natural_ventilation`
	- Fonction avant : fraction d'ouverture des fenÃªtres
	- Nouvelle fonction : `update_ventilation_v110_to_v112()`
	- Justification : la v1.12 encode la ventilation naturelle des fenÃªtres comme option canonique; la migration rapproche la fraction legacy vers `enclosure_window_natural_ventilation`.

- `permanent_spa_present` / `permanent_spa_pump_annual_kwh` / `permanent_spa_pump_usage_multiplier` / `permanent_spa_heater_type` / `permanent_spa_heater_annual_kwh` / `permanent_spa_heater_annual_therm` / `permanent_spa_heater_usage_multiplier`
	- Changement appliquÃ© : fusion vers `misc_permanent_spa`
	- Impact rÃ©sultats : aucun pour les correspondances exactes; rapprochement possible vers l'option la plus proche sinon
	- Nouveau nom si pertinent : `misc_permanent_spa`
	- Fonction avant : prÃ©sence, pompe, chauffage et multiplicateur du spa permanent dÃ©crits par plusieurs colonnes legacy
	- Nouvelle fonction : `update_pool_parameters_v110_to_v112()`
	- Justification : la v1.12 concentre les paramÃ¨tres du spa permanent dans une option unique; la migration reconstruit l'option Ã  partir des colonnes legacy et supprime ensuite ces colonnes du CSV.

- `geometry_unit_orientation`
	- Changement appliquÃ© : changement de type + renommage
	- Impact rÃ©sultats : perte de prÃ©cision mineure
	- Nouveau nom si pertinent : `geometry_unit_direction`
	- Fonction avant : angle en degrÃ©s depuis le nord (`Double`)
	- Nouvelle fonction : `update_geometry_unit_orientation_v110_to_v112()`
	- Justification : la v1.12 attend une direction canonique (`North`, `East`, `South`, etc.) plutÃ´t quâ€™un angle brut, ce qui simplifie la saisie et correspond Ã  la nouvelle mesure.

- `window_ufactor` / `window_shgc`
	- Changement appliquÃ© : fusion + renommage
	- Impact rÃ©sultats : aucun pour les correspondances exactes; rapprochement possible vers lâ€™option la plus proche sinon
	- Nouveau nom si pertinent : `enclosure_window`
	- Fonction avant : propriÃ©tÃ©s thermiques des fenÃªtres dÃ©crites par deux colonnes numÃ©riques
	- Nouvelle fonction : `update_enclosure_window_v110_to_v112()`
	- Justification : la v1.12 encode le vitrage comme option-string canonique; la migration rapproche le couple U-factor/SHGC vers lâ€™option la plus proche dans `enclosure_window.tsv`.

- `skylight_ufactor` / `skylight_shgc`
	- Changement appliquÃ© : fusion + renommage
	- Impact rÃ©sultats : aucun pour les correspondances exactes; rapprochement possible vers lâ€™option la plus proche sinon
	- Nouveau nom si pertinent : `enclosure_skylight`
	- Fonction avant : propriÃ©tÃ©s thermiques des skylights dÃ©crites par deux colonnes numÃ©riques
	- Nouvelle fonction : `update_enclosure_skylight_v110_to_v112()`
	- Justification : la v1.12 encode les skylights comme option-string canonique; la migration rapproche le couple U-factor/SHGC vers lâ€™option la plus proche dans `enclosure_skylight.tsv`.

- `window_interior_shading_summer` / `window_interior_shading_winter`
	- Changement appliquÃ© : fusion + renommage
	- Impact rÃ©sultats : aucun pour les correspondances exactes; rapprochement possible vers lâ€™option la plus proche sinon
	- Nouveau nom si pertinent : `enclosure_window_interior_shading`
	- Fonction avant : coefficients saisonniers dâ€™ombrage intÃ©rieur fournis sÃ©parÃ©ment
	- Nouvelle fonction : `update_window_interior_shading_v110_to_v112()`
	- Justification : la v1.12 attend une seule option dâ€™ombrage intÃ©rieur; la migration recolle les coefficients Ã©tÃ©/hiver vers lâ€™option canonique du TSV.

- `window_front_wwr` / `window_back_wwr` / `window_left_wwr` / `window_right_wwr` / `window_area_front` / `window_area_back` / `window_area_left` / `window_area_right`
	- Changement appliquÃ© : fusion + renommage
	- Impact rÃ©sultats : aucun pour les correspondances exactes; la migration privilÃ©gie les WWR legacy quand ils sont renseignÃ©s et bascule sur les surfaces absolues quand elles portent la valeur utile
	- Nouveau nom si pertinent : `geometry_window_areas_or_wwrs`
	- Fonction avant : fenÃªtres dÃ©crites par WWR ou surfaces absolues, faÃ§ade par faÃ§ade
	- Nouvelle fonction : `update_geometry_window_areas_or_wwrs_v110_to_v112()`
	- Justification : la v1.12 concentre la gÃ©omÃ©trie des fenÃªtres dans une chaÃ®ne comma-separated unique; la migration reconstruit cette chaÃ®ne dans lâ€™ordre front/back/left/right.

- `window_aspect_ratio`
	- Changement appliquÃ© : suppression / absorption
	- Impact rÃ©sultats : aucun dans le measure v1.12; la valeur legacy nâ€™a plus dâ€™Ã©quivalent direct et est ignorÃ©e lors de la migration
	- Nouveau nom si pertinent : aucun
	- Fonction avant : ratio hauteur / largeur des fenÃªtres
	- Nouvelle fonction : `update_geometry_window_areas_or_wwrs_v110_to_v112()`
	- Justification : la v1.12 ne consomme plus ce paramÃ¨tre; la gÃ©omÃ©trie des fenÃªtres se limite Ã  la liste des WWR ou des surfaces par faÃ§ade.

- `skylight_area_front` / `skylight_area_back` / `skylight_area_left` / `skylight_area_right`
	- Changement appliquÃ© : fusion + renommage
	- Impact rÃ©sultats : aucun pour les correspondances exactes; la migration reconstruit la liste des quatre surfaces dans lâ€™ordre front/back/left/right
	- Nouveau nom si pertinent : `geometry_skylight_areas`
	- Fonction avant : surfaces de skylights rÃ©parties sur plusieurs colonnes legacy
	- Nouvelle fonction : `update_geometry_skylight_areas_v110_to_v112()`
	- Justification : la v1.12 concentre les surfaces de skylights dans une seule chaÃ®ne comma-separated.

- `clothes_washer_present` / `clothes_washer_efficiency_type` / `clothes_washer_efficiency` / `clothes_washer_rated_annual_kwh` / `clothes_washer_label_electric_rate` / `clothes_washer_label_gas_rate` / `clothes_washer_label_annual_gas_cost` / `clothes_washer_label_usage` / `clothes_washer_capacity` / `clothes_washer_usage_multiplier` / `clothes_washer_location`
	- Changement appliquÃ© : fusion + renommage
	- Impact rÃ©sultats : aucun pour les correspondances exactes; les colonnes legacy de localisation et d'usage sont absorbÃ©es dans l'option canonique
	- Nouveau nom si pertinent : `appliance_clothes_washer`
	- Fonction avant : lave-linge dÃ©taillÃ© par efficacitÃ©, consommation, coÃ»t dâ€™Ã©tiquette, usage et localisation
	- Nouvelle fonction : `update_appliances_v110_to_v112()`
	- Justification : la v1.12 concentre le lave-linge dans une option canonique issue du TSV `appliance_clothes_washer.tsv`.

- `clothes_dryer_present` / `clothes_dryer_fuel_type` / `clothes_dryer_efficiency_type` / `clothes_dryer_efficiency` / `clothes_dryer_vented_flow_rate` / `clothes_dryer_usage_multiplier` / `clothes_dryer_location`
	- Changement appliquÃ© : fusion + renommage + suppression d'un paramÃ¨tre legacy sans Ã©quivalent direct
	- Impact rÃ©sultats : aucun pour les correspondances exactes; `clothes_dryer_vented_flow_rate` est supprimÃ© car la v1.12 ne l'expose plus directement
	- Nouveau nom si pertinent : `appliance_clothes_dryer`
	- Fonction avant : sÃ¨che-linge dÃ©taillÃ© par combustible, efficacitÃ©, mode de sÃ©chage, usage et localisation
	- Nouvelle fonction : `update_appliances_v110_to_v112()`
	- Justification : la v1.12 concentre le sÃ¨che-linge dans une option canonique issue du TSV `appliance_clothes_dryer.tsv`.

- `dishwasher_present` / `dishwasher_efficiency_type` / `dishwasher_efficiency` / `dishwasher_label_electric_rate` / `dishwasher_label_gas_rate` / `dishwasher_label_annual_gas_cost` / `dishwasher_label_usage` / `dishwasher_place_setting_capacity` / `dishwasher_usage_multiplier` / `dishwasher_location`
	- Changement appliquÃ© : fusion + renommage
	- Impact rÃ©sultats : aucun pour les correspondances exactes; les paramÃ¨tres legacy de coÃ»t et d'usage sont absorbÃ©s dans l'option canonique
	- Nouveau nom si pertinent : `appliance_dishwasher`
	- Fonction avant : lave-vaisselle dÃ©taillÃ© par efficacitÃ©, coÃ»t, capacitÃ© et usage
	- Nouvelle fonction : `update_appliances_v110_to_v112()`
	- Justification : la v1.12 condense le lave-vaisselle dans une option canonique issue du TSV `appliance_dishwasher.tsv`.

- `refrigerator_present` / `refrigerator_rated_annual_kwh` / `refrigerator_usage_multiplier` / `refrigerator_location`
	- Changement appliquÃ© : fusion + renommage
	- Impact rÃ©sultats : aucun pour les correspondances exactes; les colonnes legacy de localisation et d'usage sont absorbÃ©es dans l'option canonique
	- Nouveau nom si pertinent : `appliance_refrigerator`
	- Fonction avant : rÃ©frigÃ©rateur dÃ©taillÃ© par consommation, usage et localisation
	- Nouvelle fonction : `update_appliances_v110_to_v112()`
	- Justification : la v1.12 concentre le rÃ©frigÃ©rateur dans une option canonique issue du TSV `appliance_refrigerator.tsv`.

- `extra_refrigerator_present` / `extra_refrigerator_rated_annual_kwh` / `extra_refrigerator_usage_multiplier` / `extra_refrigerator_location`
	- Changement appliquÃ© : fusion + renommage
	- Impact rÃ©sultats : aucun pour les correspondances exactes; les colonnes legacy de localisation et d'usage sont absorbÃ©es dans l'option canonique
	- Nouveau nom si pertinent : `appliance_extra_refrigerator`
	- Fonction avant : rÃ©frigÃ©rateur additionnel dÃ©taillÃ© par consommation, usage et localisation
	- Nouvelle fonction : `update_appliances_v110_to_v112()`
	- Justification : la v1.12 concentre le rÃ©frigÃ©rateur additionnel dans une option canonique issue du TSV `appliance_extra_refrigerator.tsv`.

- `dehumidifier_type` / `dehumidifier_efficiency_type` / `dehumidifier_efficiency` / `dehumidifier_capacity` / `dehumidifier_fraction_dehumidification_load_served`
	- Changement appliquÃ© : fusion + renommage + suppression d'un paramÃ¨tre legacy sans Ã©quivalent direct
	- Impact rÃ©sultats : aucun pour les correspondances exactes; `dehumidifier_fraction_dehumidification_load_served` est supprimÃ© car la v1.12 ne l'expose plus directement
	- Nouveau nom si pertinent : `appliance_dehumidifier`
	- Fonction avant : dÃ©shumidificateur dÃ©taillÃ© par type, efficacitÃ©, capacitÃ© et part de charge servie
	- Nouvelle fonction : `update_appliances_v110_to_v112()`
	- Justification : la v1.12 concentre le dÃ©shumidificateur dans une option canonique issue du TSV `appliance_dehumidifier.tsv`.

- `dehumidifier_rh_setpoint`
	- Changement appliquÃ© : renommage
	- Impact rÃ©sultats : aucun pour les correspondances exactes
	- Nouveau nom si pertinent : `appliance_dehumidifier_setpoint`
	- Fonction avant : consigne d'humiditÃ© relative legacy
	- Nouvelle fonction : `update_appliances_v110_to_v112()`
	- Justification : la v1.12 expose ce paramÃ¨tre comme un argument dÃ©diÃ©, alimentÃ© par le TSV `appliance_dehumidifier_setpoint.tsv`.

- `overhangs_back_depth` / `overhangs_front_depth` / `overhangs_left_depth` / `overhangs_right_depth`
	- Changement appliquÃ© : fusion vers un seul argument
	- Impact rÃ©sultats : aucun
	- Nouveau nom si pertinent : `enclosure_overhangs`
	- Fonction avant : colonnes legacy dâ€™overhang par faÃ§ade
	- Nouvelle fonction : `update_enclosure_overhangs_v110_to_v112()`
	- Justification : la v1.12 expose dÃ©jÃ  `enclosure_overhangs`; la migration rassemble les anciennes colonnes dÃ©taillÃ©es et les mappe vers lâ€™option correspondante sans perdre lâ€™information fonctionnelle.

- `site_time_zone_utc_offset`
	- Changement appliquÃ© : suppression
	- Impact rÃ©sultats : aucun
	- Nouveau nom si pertinent : `TimeZone/UTCOffset` cÃ´tÃ© HPXML, mais pas comme argument CSV direct
	- Fonction avant : offset UTC fourni dans le CSV legacy
	- Nouvelle fonction : `update_site_time_zone_utc_offset_v110_to_v112()`
	- Justification : la v1.12 calcule le fuseau horaire depuis la localisation du site (zip code ou EPW) et le stocke dans la structure HPXML; le CSV de migration nâ€™expose plus ce rÃ©glage directement.

- `simulation_control_daylight_saving_enabled`
	- Changement appliquÃ© : suppression
	- Impact rÃ©sultats : aucun
	- Nouveau nom si pertinent : `TimeZone/DSTObserved` cÃ´tÃ© HPXML, mais pas comme argument CSV direct
	- Fonction avant : boolÃ©en explicite pour activer lâ€™heure dâ€™Ã©tÃ©
	- Nouvelle fonction : `update_simulation_control_daylight_saving_enabled_v110_to_v112()`
	- Justification : la v1.12 ne consomme plus ce champ dans le measure; la logique DST est dÃ©sormais dÃ©duite des mÃ©tadonnÃ©es de site et des valeurs par dÃ©faut liÃ©es au code postal ou Ã  lâ€™Ã©tat.

- `year_built`
	- Changement appliquÃ© : renommage
	- Impact rÃ©sultats : aucun
	- Nouveau nom si pertinent : `building_year_built`
	- Fonction avant : annÃ©e de construction
	- Nouvelle fonction : `update_year_built_v110_to_v112()`
	- Justification : le measure v1.12 expose le champ sous le nom `building_year_built`.