# Phase 1 — Migration OpenStudio-HPXML v1.10 → v1.12

## Objectif

Rendre SimParc compatible avec OpenStudio-HPXML v1.12 en migrant vers le nouveau
format d'arguments option-string de `BuildResidentialHPXML`, et fournir un outil
de migration des anciens CSV (v1.10) vers le nouveau format (v1.12).

---

## Changements effectués

### 1. `OpenStudio-HPXML/BuildResidentialHPXML/resources/options/*.tsv`

Extension des fichiers TSV avec des valeurs R québécoises spécifiques absentes des
options NREL standard :

| Fichier TSV | Entrées ajoutées |
|---|---|
| `enclosure_wall.tsv` | `QC Wood Stud, R-10.9` … `QC Wood Stud, R-24.5` (16 entrées) |
| `enclosure_ceiling.tsv` | `QC R-12.0` … `QC R-42.6` (12 entrées) |
| `enclosure_foundation_wall.tsv` | R-7 à R-17.1 interior/exterior (12 entrées) |
| `enclosure_floor_over_foundation.tsv` | `QC Wood Frame, R-5.3` et `R-22.6` |
| `enclosure_floor_over_garage.tsv` | `QC Wood Frame, R-5.3` et `R-22.6` |

Tous les fichiers TSV ont également été nettoyés des caractères `\r` (CRLF → LF)
pour compatibilité avec le parser CSV de Ruby 3.2 (OpenStudio 3.11).

---

### 2. `local.py`

`pd.read_csv` → `read_csv` (de `utils`) pour la lecture du CSV de bâtiments.

**Raison :** `pd.read_csv` convertit la chaîne `'None'` en `NaN`, empêchant les
valeurs comme `hvac_heating_system = 'None'` et `hvac_ducts = 'None'` d'atteindre
`hpxml_args`. La fonction `utils.read_csv` exclut `'None'` des valeurs NA.

---

### 3. `preprocessing.py`

Suppression de la ligne qui copiait `location_epw_path` dans `non_hpxml_args`
(provoquait un `KeyError` lors de la migration vers le nouveau format où cette
colonne n'existe plus dans le CSV).

---

### 4. `upgrading.py`

Réécriture des fonctions `add_ashp`, `add_mshp`, `add_gshp` pour utiliser les
nouveaux arguments option-string de v1.12 à la place des anciens arguments
détaillés séparés :

| Anciens args (v1.10) | Nouveaux args (v1.12) |
|---|---|
| `heat_pump_type` + efficacités | `hvac_heat_pump` (ex: `"Central HP, SEER2 17.0, HSPF2 8.5"`) |
| `heat_pump_backup_type/fuel/efficiency` | `hvac_heat_pump_backup` (ex: `"Integrated, Electricity, 100% Efficiency"`) |
| `heat_pump_compressor_lockout_temp` | `hvac_heat_pump_temperatures` (ex: `"5F Min Compressor Temp"`) |
| `heat_pump_fraction_heat/cool_load_served` | `hvac_heat_pump_heating/cooling_load_served` |
| `heating_system_type` | `hvac_heating_system = "None"` |
| `cooling_system_type` | `hvac_cooling_system = "None"` |

Correction de la fonction `air_leakage(df, rate)` : modifie maintenant la colonne
`enclosure_air_leakage` (format `"X ACH50"`) au lieu de l'ancienne colonne
`air_leakage_value`.

---

### 5. `utils.py`

Ajout de configuration pour utiliser les mesure du repo `OpenStudio-HPXML/` et `measures`.

---

### 6. `building.py`

Inversion de l'ordre des `measure_paths` dans l'OSW : `OpenStudio-HPXML/` en
premier (contient `BuildResidentialHPXML`, `HPXMLtoOpenStudio`,
`BuildResidentialScheduleFile`, `ReportSimulationOutput`), puis `measures/`
(contient `ModifyStochasticFilePython`).

**Raison :** `BuildResidentialHPXML` doit rester dans `OpenStudio-HPXML/` car son
`measure.rb` charge les ressources via un chemin relatif
`../HPXMLtoOpenStudio/resources/` qui n'existe que dans cette structure de
répertoire.

---

### 7. `project.yaml` 

`HPXML_SCHEMA_FILE` mis à jour vers `OpenStudio-HPXML/BuildResidentialHPXML/measure.xml`
(nouveau measure v1.12 avec les arguments option-string).

---

### 8. `tools/migrate_csv.py` *(nouveau fichier)*

Script autonome pour convertir un CSV de bâtiments du format v1.10 (arguments
HPXML détaillés) vers le format v1.12 (option-strings).

Mappings principaux implémentés :

- **Géométrie** :
  - `geometry_unit_type` + `geometry_unit_num_floors_above_grade` → option combinée
    (ex: `"Apartment Unit, 1 Story"`, `"Single-Family Detached, 2 Stories"`)
  - `geometry_attic_type` + `geometry_roof_type` → option combinée
    (ex: `"Attic, Vented, Gable"`, `"Flat Roof"`, `"Below Apartment"`)
  - `geometry_foundation_type` camelCase → spaced
    (ex: `"ConditionedBasement"` → `"Basement, Conditioned"`)
  - `geometry_unit_num_bedrooms` → entier (conversion float→int)

- **Enveloppe** :
  - `wall_type` + `wall_assembly_r` → `enclosure_wall` (match exact dans
    `enclosure_wall.tsv` par type + Assembly R-Value)
  - `ceiling_assembly_r` → `enclosure_ceiling` (match exact dans
    `enclosure_ceiling.tsv` ; `0.0` ou NaN → `"Uninsulated"`)
  - `foundation_wall_insulation_r` + `foundation_wall_insulation_location` →
    `enclosure_foundation_wall` (match exact dans TSV ; `0.0` → `"Solid Concrete,
    Uninsulated"`)
  - `floor_over_foundation_assembly_r` → `enclosure_floor_over_foundation` (match
    exact dans TSV ; `0.0` ou NaN → `None`)
  - `floor_over_garage_assembly_r` → `enclosure_floor_over_garage` (idem)
  - `window_ufactor` + `window_shgc` → `enclosure_window` (match exact U-Factor +
    SHGC dans `enclosure_window.tsv`)
  - `Infiltration` → `enclosure_air_leakage` (renommage direct) ; à défaut,
    `air_leakage_value` + `air_leakage_units` + `air_leakage_house_pressure` →
    chaîne formatée (ex: `"3.0 ACH50"`)

- **CVCA** :
  - `heating_system_type` + `heating_system_heating_efficiency` →
    `hvac_heating_system` (ex: `"Central Furnace, 80% AFUE"`) ; `ElectricResistance`
    → `"Electric Resistance"`
  - `heating_system_fuel` → `hvac_heating_system_fuel` (normalisation casse)
  - `heating_system_fraction_heat_load_served` →
    `hvac_heating_system_heating_load_served` (ex: `"100%"`)
  - `cooling_system_type` + efficiency → `hvac_cooling_system` (nearest-match SEER2
    dans `hvac_cooling_system.tsv` ; conversion SEER→SEER2 × 0.95,
    EER→SEER2 × 1.05)
  - `cooling_system_fraction_cool_load_served` →
    `hvac_cooling_system_cooling_load_served`
  - `heat_pump_type` + `heat_pump_cooling_efficiency` +
    `heat_pump_heating_efficiency` → `hvac_heat_pump` (nearest-match SEER2 + HSPF2
    combinés dans `hvac_heat_pump.tsv` ; conversions SEER→SEER2, HSPF→HSPF2 × 0.85)
  - `heat_pump_backup_type` + `heat_pump_backup_fuel` +
    `heat_pump_backup_heating_efficiency` → `hvac_heat_pump_backup`
    (ex: `"Integrated, Electricity, 100% Efficiency"`)
  - `heat_pump_compressor_lockout_temp` → `hvac_heat_pump_temperatures`
    (ex: `"5F Min Compressor Temp"`)
  - `heat_pump_fraction_heat/cool_load_served` →
    `hvac_heat_pump_heating/cooling_load_served`
  - `geothermal_loop_configuration` → `hvac_geothermal_loop` (`"Default"` pour
    vertical/horizontal, `None` si absent)
  - `HVAC Has Ducts` / `duct_leakage_value` + `duct_insulation_r_value` →
    `hvac_ducts` (nearest-match dans `hvac_ducts.tsv` ; `"No"` → `"None"`)

- **ECS** :
  - `water_heater_type` + `water_heater_fuel_type` + `water_heater_efficiency` →
    `dhw_water_heater` (nearest-match UEF dans `dhw_water_heater.tsv` ; Heat Pump →
    `"Electricity, Heat Pump, UEF X.XX"`)

- **Suppression des anciennes colonnes** : les ~60 colonnes v1.10 absorbées par les
  nouveaux option-strings sont supprimées automatiquement via `OLD_COLUMNS_TO_DROP`
  (géométrie, enveloppe, CVCA, ECS, misc).

Usage :
```bash
python tools/migrate_csv.py input_v110.csv [output_v112.csv]
```

Si `output` est omis, le fichier est écrit dans
`<répertoire_input>/v1.12/<stem>-1.12.csv`.

---

## Points d'attention pour la suite

- `hvac_heating_system_fuel` et `hvac_heating_system_heating_load_served` sont
  encore générés même quand `hvac_heating_system = 'None'` — inoffensif pour les
  cas testés mais à nettoyer dans `migrate_csv.py` pour les bâtiments bi-énergie.
- Les items `todo.md` non couverts dans cette phase : namespace HPXML
  `2023/09 → 2025/12`, `"none" → "not present"`, unités peak load kBtu/h → Btu/h,
  Dockerfile/version.rb OpenStudio 3.11, schedules conditionnels dans
  `ModifyStochasticFilePython`.
