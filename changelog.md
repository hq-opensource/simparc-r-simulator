# SimParc-R-Simulator Changelog

## [Unreleased]

### Migration Tooling Enhancement

**Date**: September 3, 2026  
**Author**: CelineDupont

#### Changed
- **tools/migrate_csv.py** — Enhanced v1.10→v1.12 migration tool:
  - ✅ Fixed critical bugs in `update_leakage_column_value()`:
    - Corrected output format from `"3.0 ACH 50"` to `"3 ACH50"` (matches TSV spec)
    - Fixed typo: `updateleakage_column_value()` → `update_leakage_column_value()`
    - Removed undefined `output_filePath` variable in column update function
  - ✅ Added `build_enclosure_air_leakage_value()` helper:
    - Properly formats values for ACH, CFM, and natural ACH units
    - Handles optional pressure parameter per TSV specification
    - Validates all input columns exist before processing
  - ✅ Now correctly constructs `enclosure_air_leakage` column from v1.10 component columns:
    - Reads: `air_leakage_value`, `air_leakage_units`, `air_leakage_house_pressure`
    - Outputs: `enclosure_air_leakage` (e.g., `"3.57 ACH50"`, `"0.2 nACH"`)
  - Added column validation with descriptive warnings for missing inputs
  - Enhanced user feedback with migration status messages


#### Known Issues Resolved
- ✅ **P4 (Migration robustness)** — `enclosure_air_leakage` construction now works correctly
  - Validates required columns exist
  - Gracefully handles missing air leakage data
  - Produces TSV-compliant option strings

#### Status Update
- ✅ P4 resolved: CSV migration now constructs `enclosure_air_leakage` correctly
- 🔴 P1 still blocking: `enclosure_air_leakage` column still needs to be created in preprocessing pipeline
- 🔴 P1b still blocking: `climate_zone_ieccs[0]` nil guard in defaults.rb:1181

---

### OpenStudio-HPXML v1.12 Compatibility Updates

**Date**: September 1, 2026  
**Commit**: 00f2ade562fd2875da6b90571da438882d077bde  
**Author**: CelineDupont

#### Changed
- **ParseHPXMLinputs/hpxml-args-constraints.json** — Updated HPXML v5.0-rc1 breaking change:
  - Replaced `"none"` with `"not present"` in `Choices` and `Default Value` for:
    - `wall_siding_type` (maps to HPXML `Siding`)
    - `window_interior_shading_type` (maps to HPXML `InteriorShading/Type`)
    - `window_exterior_shading_type` (maps to HPXML `ExteriorShading/Type`)
    - `pool_heater_type` (maps to HPXML `Heater/Type`)
    - `permanent_spa_heater_type` (maps to HPXML `Heater/Type`)


#### Status
- ✅ v1.12 HPXML value namespace change implemented
- ⏳ Pending: P1 fix for air leakage schema mapping (`enclosure_air_leakage` column construction in preprocessing)
- ⏳ Pending: P1b guard nil on `climate_zone_ieccs[0]` in defaults.rb:1181
- ⏳ Pending: P2 verification of kBtu/hr → Btu/hr peak load output column rename

---

### Project Configuration Updates

**Date**: August 18, 2026  
**Commit**: 3ca3c2901d6fe2fbcda3e9ebf2d448a04a8f6e6f  
**Author**: Benoit Delcroix

#### Changed
- **project.yaml** — Disabled upgrade settings by default:
  - Changed `UPGRADES_SETTINGS:` (active) → `UPGRADES_SETTINGS: null` (disabled)
  - Commented out all 12 upgrade definitions (roof insulation, air leakage reduction, heating setpoint, ASHP, GSHP, MSHP, etc.)
  - Reason: Simplifies baseline simulations and improves runtime by skipping upgrade branch logic

#### Notes
- Upgrade definitions remain in code for future re-enablement when needed
- Baseline simulations now run without applying any efficiency upgrades

---

## Known Issues & In-Progress Tasks

### 🔴 Critical (P1)
1. **Air leakage schema mismatch** — CSV uses v1.10 `air_leakage_*` columns but measure expects `enclosure_air_leakage` TSV argument. This causes `leakiness_description` to default to `"average"` in HPXML, which triggers a crash in `Defaults.apply_infiltration` when weather data is Canadian (missing IECC climate zone).
   - **Fix required**: Add logic to `preprocessing.py` to construct `enclosure_air_leakage` column (using migration logic now available in `tools/migrate_csv.py`)
   - **File**: `preprocessing.py` → add `build_enclosure_air_leakage_value()` equivalent
   - **Blocking**: All v1.12 simulations

2. **Climate zone guard nil** — `defaults.rb:1181` accesses `climate_zone_ieccs[0].zone` without checking if array is empty.
   - **Fix required**: Add nil guard (see pattern at lines 3084, 3404)
   - **File**: `OpenStudio-HPXML/HPXMLtoOpenStudio/resources/defaults.rb`
   - **Blocking**: v1.12 simulations with Canadian weather

### 🔴 Critical (P2)
3. **Peak load output unit change** — kBtu/hr → Btu/hr in v1.12. Verify postprocessing chain doesn't reference old column names.
   - **Status**: No references found yet, but needs confirmation after P1 fix allows full simulation runs
   - **Files to check**: `postprocessing.py`, `postprocess/Analyse.py`

### 🟡 Moderate (P3)
4. **HVAC heating system fuel cleanup** — `tools/migrate_csv.py` generates spurious `hvac_heating_system_fuel` when `hvac_heating_system = 'None'`
   - **Status**: Not yet addressed
   - **File**: `tools/migrate_csv.py`

### ✅ Resolved (P4)
5. **CSV migration robustness** — ✅ **RESOLVED** (Sep 3, 2026)
   - `tools/migrate_csv.py` now correctly constructs `enclosure_air_leakage` option strings
   - Proper validation and error handling added
   - Can be used as reference for P1 implementation in `preprocessing.py`

---

## Version History

- **v1.12.0** — OpenStudio-HPXML v1.12.0 (in progress)
  - HPXML namespace: `http://hpxmlonline.com/2025/12`
  - Breaking changes: "none" → "not present", kBtu/hr → Btu/hr peak loads
- **v1.11.0** — OpenStudio 3.11 / EnergyPlus 25.2
- **v1.10.x** — Previous stable baseline
