# Instructions

Documenter les colonnes migrées. Indiquer l'ancien nom, le changement appliqué (renommage, fusion, changement de type, suppression, autre), l'impact sur les résultats, le nouveau nom si pertinent, la fonction avant, la nouvelle fonction si pertinent, et la justification de la modification.

# Détail

## Premières colonnes migrées

La liste ci-dessous est triée par ordre alphabétique du nom de colonne d'origine.

- `air_leakage_value` / `air_leakage_units` / `air_leakage_house_pressure`
	- Changement appliqué : fusion + renommage
	- Impact résultats : aucun pour les valeurs reconnues; légère approximation possible lors du rapprochement vers l'option canonique
	- Nouveau nom si pertinent : `enclosure_air_leakage`
	- Fonction avant : fuite d'air décrite par valeur, unité et pression de test
	- Nouvelle fonction : `update_air_leakage_v110_to_v112()`
	- Justification : la v1.12 encode la fuite d'air comme option-string canonique; la migration reconstruit la valeur legacy puis la rapproche de l'option la plus proche dans le TSV.

- `geometry_attic_type` / `geometry_roof_type`
	- Changement appliqué : fusion + renommage
	- Impact résultats : aucun
	- Nouveau nom si pertinent : `geometry_attic_type`
	- Fonction avant : type d'attic combiné au type de toit
	- Nouvelle fonction : `update_geometry_attic_v110_to_v112()`
	- Justification : la v1.12 porte la logique de toit dans les noms d'options d'attic; `geometry_roof_type` est absorbé pour produire l'option finale.

- `geometry_average_ceiling_height`
	- Changement appliqué : changement de type + renommage
	- Impact résultats : perte de précision mineure
	- Nouveau nom si pertinent : `geometry_ceiling_height`
	- Fonction avant : valeur libre en pieds (`Double`)
	- Nouvelle fonction : `update_geometry_average_ceiling_height_v110_to_v112()`
	- Justification : la v1.12 remplace le champ libre par une liste d’options prédéfinies (`Choice`) afin d’aligner l’interface avec les options du measure.

- `geometry_building_num_units`
	- Changement appliqué : autre
	- Impact résultats : aucun
	- Nouveau nom si pertinent : `BuildingConstruction/NumberofUnitsInBuilding` côté HPXML, mais pas comme argument CSV direct
	- Fonction avant : nombre d’unités fourni explicitement
	- Nouvelle fonction : `update_geometry_building_num_units_v110_to_v112()`
	- Justification : le measure ne l’expose plus comme argument direct, mais le backend HPXML le consomme encore et l’écrit vers `NumberofUnitsInBuilding`.

- `geometry_foundation_height` / `geometry_foundation_height_above_grade` / `geometry_rim_joist_height` / `geometry_foundation_type`
	- Changement appliqué : fusion + renommage
	- Impact résultats : aucun pour les cas standard; les hauteurs servent à sélectionner la variante de fondation appropriée
	- Nouveau nom si pertinent : `geometry_foundation_type`
	- Fonction avant : type de fondation et hauteurs associées
	- Nouvelle fonction : `update_geometry_foundation_v110_to_v112()`
	- Justification : la v1.12 encode les variantes de fondation dans les noms d'options; les hauteurs legacy servent à choisir la bonne option plutôt qu'à rester en colonnes séparées.

- `foundation_wall_type` / `foundation_wall_insulation_r` / `foundation_wall_insulation_location` / `foundation_wall_insulation_distance_to_top`
	- Changement appliqué : fusion + renommage
	- Impact résultats : aucun pour les correspondances exactes; rapprochement possible vers l’option la plus proche sinon
	- Nouveau nom si pertinent : `enclosure_foundation_wall`
	- Fonction avant : type de mur de fondation et champs d’isolation détaillés
	- Nouvelle fonction : `update_enclosure_foundation_wall_v110_to_v112()`
	- Justification : la v1.12 concentre le mur de fondation dans un choix canonique; la migration combine le type, la valeur R, la position de l’isolant et la distance au sommet pour retrouver l’option la plus proche dans `enclosure_foundation_wall.tsv`.

- `floor_type` / `slab_perimeter_insulation_r` / `slab_under_insulation_r`
	- Changement appliqué : suppression + fusion partielle vers `enclosure_slab`
	- Impact résultats : aucun pour les cas simples; approximation possible lorsque les isolations legacy sont ambiguës ou simultanées
	- Nouveau nom si pertinent : `enclosure_slab`
	- Fonction avant : type de plancher legacy plus deux R-values de dalle séparées
	- Nouvelle fonction : `update_enclosure_slab_v110_to_v112()`
	- Justification : la v1.12 représente la dalle comme option-string canonique. La migration reconstruit l’option à partir des R-values legacy, choisit une représentation cohérente quand les deux isolations sont présentes, et supprime ensuite les colonnes legacy. `floor_type` n’a plus d’équivalent direct dans le measure v1.12 et est absorbé par le backend.

- `wall_type` / `wall_assembly_r`
	- Changement appliqué : fusion + renommage
	- Impact résultats : aucun pour les correspondances exactes; rapprochement possible vers l’option la plus proche sinon. Valider si l'impact est majeur.
	- Nouveau nom si pertinent : `enclosure_wall`
	- Fonction avant : type de mur et R-value d’assemblage séparés
	- Nouvelle fonction : `update_enclosure_wall_v110_to_v112()`
	- Justification : la v1.12 encode le type de mur et son isolation d’assemblage dans un seul choix; la migration choisit l’option la plus proche dans `enclosure_wall.tsv`.

- `ceiling_assembly_r`
	- Changement appliqué : renommage
	- Impact résultats : aucun pour les correspondances exactes; rapprochement possible vers l’option la plus proche sinon
    Valider si l'impact est majeur.
	- Nouveau nom si pertinent : `enclosure_ceiling`
	- Fonction avant : R-value d’assemblage du plafond
	- Nouvelle fonction : `update_enclosure_ceiling_v110_to_v112()`
	- Justification : la v1.12 attend un choix canonique de plafond; la migration rapproche le R-value legacy vers `enclosure_ceiling.tsv`.

- `floor_over_foundation_assembly_r`
	- Changement appliqué : renommage
	- Impact résultats : aucun pour les correspondances exactes; rapprochement possible vers l’option la plus proche sinon
    Valider si l'impact est majeur.
	- Nouveau nom si pertinent : `enclosure_floor_over_foundation`
	- Fonction avant : R-value d’assemblage du plancher sur fondation
	- Nouvelle fonction : `update_enclosure_floor_over_foundation_v110_to_v112()`
	- Justification : la v1.12 encode ce plancher dans un choix canonique; la migration rapproche le R-value legacy vers `enclosure_floor_over_foundation.tsv`.

- `floor_over_garage_assembly_r`
	- Changement appliqué : renommage
	- Impact résultats : aucun pour les correspondances exactes; rapprochement possible vers l’option la plus proche sinon
    Valider si l'impact est majeur.
	- Nouveau nom si pertinent : `enclosure_floor_over_garage`
	- Fonction avant : R-value d’assemblage du plancher sur garage
	- Nouvelle fonction : `update_enclosure_floor_over_garage_v110_to_v112()`
	- Justification : la v1.12 encode ce plancher dans un choix canonique; la migration rapproche le R-value legacy vers `enclosure_floor_over_garage.tsv`.

- `geometry_unit_cfa`
	- Changement appliqué : renommage
	- Impact résultats : aucun
	- Nouveau nom si pertinent : `geometry_unit_conditioned_floor_area`
	- Fonction avant : aire conditionnée du logement
	- Nouvelle fonction : `update_geometry_unit_cfa_v110_to_v112()`
	- Justification : le measure v1.12 utilise `geometry_unit_conditioned_floor_area` pour l’aire de plancher conditionnée.

- `geometry_unit_num_floors_above_grade` / `geometry_unit_type`
	- Changement appliqué : fusion + renommage
	- Impact résultats : aucun
	- Nouveau nom si pertinent : `geometry_unit_type`
	- Fonction avant : type d'unité et nombre d'étages au-dessus du sol
	- Nouvelle fonction : `update_geometry_unit_v110_to_v112()`
	- Justification : la v1.12 encode le type d'unité et le nombre d'étages dans une seule option; la migration combine les deux colonnes legacy pour retrouver l'option canonique.

- `pool_present` / `pool_pump_annual_kwh` / `pool_pump_usage_multiplier` / `pool_heater_type` / `pool_heater_annual_kwh` / `pool_heater_annual_therm` / `pool_heater_usage_multiplier`
	- Changement appliqué : fusion vers `misc_pool`
	- Impact résultats : aucun pour les correspondances exactes; rapprochement possible vers l'option la plus proche sinon
	- Nouveau nom si pertinent : `misc_pool`
	- Fonction avant : présence, pompe, chauffage et multiplicateur de la piscine décrits par plusieurs colonnes legacy
	- Nouvelle fonction : `update_pool_parameters_v110_to_v112()`
	- Justification : la v1.12 concentre les paramètres piscine dans une option unique; la migration reconstruit l'option à partir des colonnes legacy et supprime ensuite ces colonnes du CSV.

- `water_heater_fuel_type` / `water_heater_efficiency_type` / `water_heater_efficiency` / `water_heater_recovery_efficiency` / `water_heater_standby_loss` / `water_heater_jacket_rvalue` / `water_heater_setpoint_temperature` / `water_heater_type`
	- Changement appliqué : fusion + renommage + suppression de paramètres legacy non repris
	- Impact résultats : aucun pour les correspondances exactes; approximation possible pour les combinaisons legacy qui n'ont plus d'équivalent strict
	- Nouveau nom si pertinent : `dhw_water_heater`
	- Fonction avant : type de chauffe-eau, combustible, efficacité et paramètres annexes legacy
	- Nouvelle fonction : `update_dhw_water_heater_v110_to_v112()`
	- Justification : la v1.12 concentre l’équipement ECS dans une option canonique; la migration choisit l’option la plus proche dans `dhw_water_heater.tsv` à partir du type, du combustible et de l’efficacité, puis supprime les colonnes legacy non reprises.

- `water_heater_location`
	- Changement appliqué : renommage
	- Impact résultats : aucun
	- Nouveau nom si pertinent : `dhw_water_heater_location`
	- Fonction avant : localisation du chauffe-eau
	- Nouvelle fonction : `update_dhw_water_heater_v110_to_v112()`
	- Justification : la v1.12 garde un argument dédié à la localisation du chauffe-eau; la migration applique une correspondance directe vers les emplacements canoniques, avec fallback sur `Default`.


- `mech_vent_fan_type` / `mech_vent_flow_rate` / `mech_vent_hours_in_operation` / `mech_vent_recovery_efficiency_type` / `mech_vent_total_recovery_efficiency` / `mech_vent_sensible_recovery_efficiency` / `mech_vent_fan_power` / `mech_vent_num_units_served`
	- Changement appliqué : fusion + renommage + absorption partielle des détails legacy non repris
	- Impact résultats : aucun pour les correspondances exactes; approximation possible si les rendements legacy ne tombent pas sur une option canonique exacte
	- Nouveau nom si pertinent : `ventilation_mechanical`
	- Fonction avant : ventilation mécanique répartie sur plusieurs colonnes legacy
	- Nouvelle fonction : `update_ventilation_v110_to_v112()`
	- Justification : la v1.12 regroupe la ventilation mécanique dans une option canonique; la migration remappe le système via le TSV `ventilation_mechanical.tsv`.

- `whole_house_fan_present` / `whole_house_fan_flow_rate` / `whole_house_fan_power`
	- Changement appliqué : fusion + renommage + suppression des détails legacy non repris
	- Impact résultats : aucun pour les correspondances exactes; approximation possible si le couple débit / puissance ne correspond pas exactement à une option canonique
	- Nouveau nom si pertinent : `ventilation_whole_house_fan`
	- Fonction avant : ventilateur global décrit par présence, débit et puissance
	- Nouvelle fonction : `update_ventilation_v110_to_v112()`
	- Justification : la v1.12 encode le ventilateur global comme option canonique; la migration rapproche le débit et la puissance vers l’option la plus proche dans `ventilation_whole_house_fan.tsv`.

- `kitchen_fans_start_hour`
	- Changement appliqué : absorption par défaut
	- Impact résultats : aucun pour le comportement fonctionnel; la valeur legacy est conservée dans le journal d'approximation pour traçabilité
	- Nouveau nom si pertinent : `ventilation_kitchen`
	- Fonction avant : heure de démarrage du ventilateur de cuisine
	- Nouvelle fonction : `update_ventilation_v110_to_v112()`
	- Justification : la v1.12 n’expose pas de champ équivalent direct pour cette granularité; la migration utilise `Default` et logge la valeur legacy.

- `bathroom_fans_start_hour`
	- Changement appliqué : absorption par défaut
	- Impact résultats : aucun pour le comportement fonctionnel; la valeur legacy est conservée dans le journal d'approximation pour traçabilité
	- Nouveau nom si pertinent : `ventilation_bathroom`
	- Fonction avant : heure de démarrage du ventilateur de salle de bains
	- Nouvelle fonction : `update_ventilation_v110_to_v112()`
	- Justification : la v1.12 n’expose pas de champ équivalent direct pour cette granularité; la migration utilise `Default` et logge la valeur legacy.

- `window_fraction_operable`
	- Changement appliqué : renommage
	- Impact résultats : aucun pour les correspondances exactes; rapprochement possible vers l'option la plus proche sinon
	- Nouveau nom si pertinent : `enclosure_window_natural_ventilation`
	- Fonction avant : fraction d'ouverture des fenêtres
	- Nouvelle fonction : `update_ventilation_v110_to_v112()`
	- Justification : la v1.12 encode la ventilation naturelle des fenêtres comme option canonique; la migration rapproche la fraction legacy vers `enclosure_window_natural_ventilation`.

- `permanent_spa_present` / `permanent_spa_pump_annual_kwh` / `permanent_spa_pump_usage_multiplier` / `permanent_spa_heater_type` / `permanent_spa_heater_annual_kwh` / `permanent_spa_heater_annual_therm` / `permanent_spa_heater_usage_multiplier`
	- Changement appliqué : fusion vers `misc_permanent_spa`
	- Impact résultats : aucun pour les correspondances exactes; rapprochement possible vers l'option la plus proche sinon
	- Nouveau nom si pertinent : `misc_permanent_spa`
	- Fonction avant : présence, pompe, chauffage et multiplicateur du spa permanent décrits par plusieurs colonnes legacy
	- Nouvelle fonction : `update_pool_parameters_v110_to_v112()`
	- Justification : la v1.12 concentre les paramètres du spa permanent dans une option unique; la migration reconstruit l'option à partir des colonnes legacy et supprime ensuite ces colonnes du CSV.

- `geometry_unit_orientation`
	- Changement appliqué : changement de type + renommage
	- Impact résultats : perte de précision mineure
	- Nouveau nom si pertinent : `geometry_unit_direction`
	- Fonction avant : angle en degrés depuis le nord (`Double`)
	- Nouvelle fonction : `update_geometry_unit_orientation_v110_to_v112()`
	- Justification : la v1.12 attend une direction canonique (`North`, `East`, `South`, etc.) plutôt qu’un angle brut, ce qui simplifie la saisie et correspond à la nouvelle mesure.

- `window_ufactor` / `window_shgc`
	- Changement appliqué : fusion + renommage
	- Impact résultats : aucun pour les correspondances exactes; rapprochement possible vers l’option la plus proche sinon
	- Nouveau nom si pertinent : `enclosure_window`
	- Fonction avant : propriétés thermiques des fenêtres décrites par deux colonnes numériques
	- Nouvelle fonction : `update_enclosure_window_v110_to_v112()`
	- Justification : la v1.12 encode le vitrage comme option-string canonique; la migration rapproche le couple U-factor/SHGC vers l’option la plus proche dans `enclosure_window.tsv`.

- `skylight_ufactor` / `skylight_shgc`
	- Changement appliqué : fusion + renommage
	- Impact résultats : aucun pour les correspondances exactes; rapprochement possible vers l’option la plus proche sinon
	- Nouveau nom si pertinent : `enclosure_skylight`
	- Fonction avant : propriétés thermiques des skylights décrites par deux colonnes numériques
	- Nouvelle fonction : `update_enclosure_skylight_v110_to_v112()`
	- Justification : la v1.12 encode les skylights comme option-string canonique; la migration rapproche le couple U-factor/SHGC vers l’option la plus proche dans `enclosure_skylight.tsv`.

- `window_interior_shading_summer` / `window_interior_shading_winter`
	- Changement appliqué : fusion + renommage
	- Impact résultats : aucun pour les correspondances exactes; rapprochement possible vers l’option la plus proche sinon
	- Nouveau nom si pertinent : `enclosure_window_interior_shading`
	- Fonction avant : coefficients saisonniers d’ombrage intérieur fournis séparément
	- Nouvelle fonction : `update_window_interior_shading_v110_to_v112()`
	- Justification : la v1.12 attend une seule option d’ombrage intérieur; la migration recolle les coefficients été/hiver vers l’option canonique du TSV.

- `window_front_wwr` / `window_back_wwr` / `window_left_wwr` / `window_right_wwr` / `window_area_front` / `window_area_back` / `window_area_left` / `window_area_right`
	- Changement appliqué : fusion + renommage
	- Impact résultats : aucun pour les correspondances exactes; la migration privilégie les WWR legacy quand ils sont renseignés et bascule sur les surfaces absolues quand elles portent la valeur utile
	- Nouveau nom si pertinent : `geometry_window_areas_or_wwrs`
	- Fonction avant : fenêtres décrites par WWR ou surfaces absolues, façade par façade
	- Nouvelle fonction : `update_geometry_window_areas_or_wwrs_v110_to_v112()`
	- Justification : la v1.12 concentre la géométrie des fenêtres dans une chaîne comma-separated unique; la migration reconstruit cette chaîne dans l’ordre front/back/left/right.

- `window_aspect_ratio`
	- Changement appliqué : suppression / absorption
	- Impact résultats : aucun dans le measure v1.12; la valeur legacy n’a plus d’équivalent direct et est ignorée lors de la migration
	- Nouveau nom si pertinent : aucun
	- Fonction avant : ratio hauteur / largeur des fenêtres
	- Nouvelle fonction : `update_geometry_window_areas_or_wwrs_v110_to_v112()`
	- Justification : la v1.12 ne consomme plus ce paramètre; la géométrie des fenêtres se limite à la liste des WWR ou des surfaces par façade.

- `skylight_area_front` / `skylight_area_back` / `skylight_area_left` / `skylight_area_right`
	- Changement appliqué : fusion + renommage
	- Impact résultats : aucun pour les correspondances exactes; la migration reconstruit la liste des quatre surfaces dans l’ordre front/back/left/right
	- Nouveau nom si pertinent : `geometry_skylight_areas`
	- Fonction avant : surfaces de skylights réparties sur plusieurs colonnes legacy
	- Nouvelle fonction : `update_geometry_skylight_areas_v110_to_v112()`
	- Justification : la v1.12 concentre les surfaces de skylights dans une seule chaîne comma-separated.

- `clothes_washer_present` / `clothes_washer_efficiency_type` / `clothes_washer_efficiency` / `clothes_washer_rated_annual_kwh` / `clothes_washer_label_electric_rate` / `clothes_washer_label_gas_rate` / `clothes_washer_label_annual_gas_cost` / `clothes_washer_label_usage` / `clothes_washer_capacity` / `clothes_washer_usage_multiplier` / `clothes_washer_location`
	- Changement appliqué : fusion + renommage
	- Impact résultats : aucun pour les correspondances exactes; les colonnes legacy de localisation et d'usage sont absorbées dans l'option canonique
	- Nouveau nom si pertinent : `appliance_clothes_washer`
	- Fonction avant : lave-linge détaillé par efficacité, consommation, coût d’étiquette, usage et localisation
	- Nouvelle fonction : `update_appliances_v110_to_v112()`
	- Justification : la v1.12 concentre le lave-linge dans une option canonique issue du TSV `appliance_clothes_washer.tsv`.

- `clothes_dryer_present` / `clothes_dryer_fuel_type` / `clothes_dryer_efficiency_type` / `clothes_dryer_efficiency` / `clothes_dryer_vented_flow_rate` / `clothes_dryer_usage_multiplier` / `clothes_dryer_location`
	- Changement appliqué : fusion + renommage + suppression d'un paramètre legacy sans équivalent direct
	- Impact résultats : aucun pour les correspondances exactes; `clothes_dryer_vented_flow_rate` est supprimé car la v1.12 ne l'expose plus directement
	- Nouveau nom si pertinent : `appliance_clothes_dryer`
	- Fonction avant : sèche-linge détaillé par combustible, efficacité, mode de séchage, usage et localisation
	- Nouvelle fonction : `update_appliances_v110_to_v112()`
	- Justification : la v1.12 concentre le sèche-linge dans une option canonique issue du TSV `appliance_clothes_dryer.tsv`.

- `dishwasher_present` / `dishwasher_efficiency_type` / `dishwasher_efficiency` / `dishwasher_label_electric_rate` / `dishwasher_label_gas_rate` / `dishwasher_label_annual_gas_cost` / `dishwasher_label_usage` / `dishwasher_place_setting_capacity` / `dishwasher_usage_multiplier` / `dishwasher_location`
	- Changement appliqué : fusion + renommage
	- Impact résultats : aucun pour les correspondances exactes; les paramètres legacy de coût et d'usage sont absorbés dans l'option canonique
	- Nouveau nom si pertinent : `appliance_dishwasher`
	- Fonction avant : lave-vaisselle détaillé par efficacité, coût, capacité et usage
	- Nouvelle fonction : `update_appliances_v110_to_v112()`
	- Justification : la v1.12 condense le lave-vaisselle dans une option canonique issue du TSV `appliance_dishwasher.tsv`.

- `refrigerator_present` / `refrigerator_rated_annual_kwh` / `refrigerator_usage_multiplier` / `refrigerator_location`
	- Changement appliqué : fusion + renommage
	- Impact résultats : aucun pour les correspondances exactes; les colonnes legacy de localisation et d'usage sont absorbées dans l'option canonique
	- Nouveau nom si pertinent : `appliance_refrigerator`
	- Fonction avant : réfrigérateur détaillé par consommation, usage et localisation
	- Nouvelle fonction : `update_appliances_v110_to_v112()`
	- Justification : la v1.12 concentre le réfrigérateur dans une option canonique issue du TSV `appliance_refrigerator.tsv`.

- `extra_refrigerator_present` / `extra_refrigerator_rated_annual_kwh` / `extra_refrigerator_usage_multiplier` / `extra_refrigerator_location`
	- Changement appliqué : fusion + renommage
	- Impact résultats : aucun pour les correspondances exactes; les colonnes legacy de localisation et d'usage sont absorbées dans l'option canonique
	- Nouveau nom si pertinent : `appliance_extra_refrigerator`
	- Fonction avant : réfrigérateur additionnel détaillé par consommation, usage et localisation
	- Nouvelle fonction : `update_appliances_v110_to_v112()`
	- Justification : la v1.12 concentre le réfrigérateur additionnel dans une option canonique issue du TSV `appliance_extra_refrigerator.tsv`.

- `dehumidifier_type` / `dehumidifier_efficiency_type` / `dehumidifier_efficiency` / `dehumidifier_capacity` / `dehumidifier_fraction_dehumidification_load_served`
	- Changement appliqué : fusion + renommage + suppression d'un paramètre legacy sans équivalent direct
	- Impact résultats : aucun pour les correspondances exactes; `dehumidifier_fraction_dehumidification_load_served` est supprimé car la v1.12 ne l'expose plus directement
	- Nouveau nom si pertinent : `appliance_dehumidifier`
	- Fonction avant : déshumidificateur détaillé par type, efficacité, capacité et part de charge servie
	- Nouvelle fonction : `update_appliances_v110_to_v112()`
	- Justification : la v1.12 concentre le déshumidificateur dans une option canonique issue du TSV `appliance_dehumidifier.tsv`.

- `dehumidifier_rh_setpoint`
	- Changement appliqué : renommage
	- Impact résultats : aucun pour les correspondances exactes
	- Nouveau nom si pertinent : `appliance_dehumidifier_setpoint`
	- Fonction avant : consigne d'humidité relative legacy
	- Nouvelle fonction : `update_appliances_v110_to_v112()`
	- Justification : la v1.12 expose ce paramètre comme un argument dédié, alimenté par le TSV `appliance_dehumidifier_setpoint.tsv`.

- `overhangs_back_depth` / `overhangs_front_depth` / `overhangs_left_depth` / `overhangs_right_depth`
	- Changement appliqué : fusion vers un seul argument
	- Impact résultats : aucun
	- Nouveau nom si pertinent : `enclosure_overhangs`
	- Fonction avant : colonnes legacy d’overhang par façade
	- Nouvelle fonction : `update_enclosure_overhangs_v110_to_v112()`
	- Justification : la v1.12 expose déjà `enclosure_overhangs`; la migration rassemble les anciennes colonnes détaillées et les mappe vers l’option correspondante sans perdre l’information fonctionnelle.

- `site_time_zone_utc_offset`
	- Changement appliqué : suppression
	- Impact résultats : aucun
	- Nouveau nom si pertinent : `TimeZone/UTCOffset` côté HPXML, mais pas comme argument CSV direct
	- Fonction avant : offset UTC fourni dans le CSV legacy
	- Nouvelle fonction : `update_site_time_zone_utc_offset_v110_to_v112()`
	- Justification : la v1.12 calcule le fuseau horaire depuis la localisation du site (zip code ou EPW) et le stocke dans la structure HPXML; le CSV de migration n’expose plus ce réglage directement.

- `simulation_control_daylight_saving_enabled`
	- Changement appliqué : suppression
	- Impact résultats : aucun
	- Nouveau nom si pertinent : `TimeZone/DSTObserved` côté HPXML, mais pas comme argument CSV direct
	- Fonction avant : booléen explicite pour activer l’heure d’été
	- Nouvelle fonction : `update_simulation_control_daylight_saving_enabled_v110_to_v112()`
	- Justification : la v1.12 ne consomme plus ce champ dans le measure; la logique DST est désormais déduite des métadonnées de site et des valeurs par défaut liées au code postal ou à l’état.

- `year_built`
	- Changement appliqué : renommage
	- Impact résultats : aucun
	- Nouveau nom si pertinent : `building_year_built`
	- Fonction avant : année de construction
	- Nouvelle fonction : `update_year_built_v110_to_v112()`
	- Justification : le measure v1.12 expose le champ sous le nom `building_year_built`.