
## OpenStudio-HPXML v1.12.0

__Features__
- HVAC updates:
  - Adds a warning if there are more than 300 unmet hours for heating or cooling; setpoint tolerance increased from 0.36 deg-F (0.2 deg-C) to 0.5 deg-F.
  - Dual-fuel heat pumps with switchover temperatures > 25F are now autosized based on 25F to allow some additional heating capacity buffer.
  - Improves handling of duct leakage specified using cfm25/cfm50.
  - Allows multiple ground-source heat pumps attached to a single geothermal loop; yields runtime speed improvements.
  - Crankcase heating energy is now disabled during unavailable periods, e.g., power outages.
  - Adds advanced research feature to model latent degradation for cooling systems, including an input to specify an HVAC blower-off delay.
- Output updates:
  - **Breaking change**: Annual peak load outputs for heating and cooling now use units of Btu/h instead of kBtu/h for consistency with other outputs.
  - **Breaking change**: Replaces "UnitX" prefixes with Building IDs in whole SFA/MF building timeseries outputs.
  - For whole SFA/MF building simulations, reports energy/fuel use by dwelling unit (i.e., "Dwelling Unit Energy Use: \*" and "Dwelling Unit Fuel Use: \*"). Timeseries outputs are also available.
  - Allows calculating utility bills for homes with HVAC distribution systems using simplified heating/cooling DSE values (previously unsupported).
- Whole SFA/MF buildings:
  - Allows modeling batteries in individual dwelling units (previously unsupported).
- Utility bill calculations:
  - Updated default state-average utility rates to EIA State Energy Data System (SEDS) 2024 data.
  - Updates `openei_rates.zip` with the latest residential utility rates from the [OpenEI U.S. Utility Rate database](https://apps.openei.org/USURDB/).
- Allows "other" for `SoilType`; adds variation to dry/wet soil conductivity and diffusivity values for unknown/other/loam soil types.
- Updates schematron validation error messages to be more user friendly.
- Adds a `run_simulation.rb --ems-debug` argument to generate the EnergyPlus EDD file for debugging EMS programs.

__Bugfixes__
- Fixes a misleading warning about adjusting inverted setpoints when heating setpoint is greater than cooling setpoint during non-overlapping heating/cooling seasons.
- Fixes possible incorrect unmet hours outputs for unavailable periods with no space heating only (or no space cooling only).
- Fixes PanHeaterControlType="heat pump mode" incorrectly disallowed for mini-split heat pumps.
- Fixes the design cooling temperature calculations for some vented attic roof types (shingles, plastic/rubber/synthetic sheeting, concrete, cool roof, expanded polystyrene sheathing)
- Fixes unit multiplier ignored for EV charging using `Vehicles`.
- Fixes handling of battery losses in the battery resilience output.
- Fixes handling of zero occupants (i.e., unoccupied dwelling unit):
  - Fixes lighting and plug/fuel load energy use to not be zeroed out when a kWh/year or therm/year value is provided.
  - Fixes pool/spa energy use to be zeroed out when a kWh/year or therm/year value is not provided, or when there is a "Vacancy" unavailable period.
- Fixes incorrect hot water (gallons) output for solar thermal systems using `SolarFraction`.
- Small bugfixes when using the on/off thermostat deadband advanced research feature:
  - Fixes unmet hours outputs, which could be missing some periods of unmet hours.
  - Fixes timeseries outputs for heating/cooling setpoints.
- Fixes logic in HP multi-stage backup advanced research feature.
- Fixes PV grid connection fee applying in utility bill calculation even if the home has no PV.
- Fixes possible "Failed to process String" EnergyPlus error when requesting component loads.
- Fixes ducts in manufactured home belly from being incorrectly modeled as if they were outside.

## OpenStudio-HPXML v1.11.1

__Bugfixes__
- Fixes heat pump heating performance sensitivity to indoor temperatures.

## OpenStudio-HPXML v1.11.0

__Features__
- Updates to OpenStudio 3.11/EnergyPlus 25.2.
- Updates to HPXML v5.0-rc1.
  - **Breaking change**: HPXML namespace changed from http://hpxmlonline.com/2023/09 to http://hpxmlonline.com/2025/12.
  - **Breaking change**: Replaces "none" with "not present" for `InteriorFinish/Type`, `Siding`, `ExteriorShading/Type`, `InteriorShading/Type`, `Pool/Type`, `PermanentSpa/Type`, `Pump/Type`, and `Heater/Type`.
  - Allows "stone veneer" for `Wall/Siding` and `RimJoist/Siding`.
  - Allows "medium light" for `Roof/RoofColor`, `RimJoist/Color`, and `Wall/Color`.
  - Allows `SpecificLeakageArea` for air infiltration measurements.
- BuildResidentialHPXML measure:
  - **Breaking change**: New, simpler, easier to use option-based arguments (rather than detailed property arguments).
  - Automatically adjusts garage dimensions for dwelling units with small footprints to avoid errors.
- Heat pump updates:
  - Updates default heating capacities at 17F per RESNET HERS Addendum 82 and NEEP database.
  - Updates supplemental heating energy use during defrost based on RESNET HERS Addendum 82.
  - Updates shared pump power for ground-source heat pumps on a shared recirculation loop to cycle with heating/cooling load rather than operate continuously per RESNET HERS Addendum 94.
  - Allows desuperheaters to be used with the experimental ground-source heat pump model.
  - Adds `PanHeaterControlType="heat pump mode"`, in which the pan heater will run when the HP is running (and the outdoor temperature is below 32F).
  - Updates `PanHeaterControlType="continuous"` to avoid pan heater operation when the outdoor temperature is below the minimum compressor temperature.
- Allows optional `UsageMultiplier` for electric vehicles described using `Vehicles`.
- Water heater improvements:
  - Allows HPWHs to have exhaust air ducted to the outside using `HPWHDucting/ExhaustAirTermination="outside"`.
  - Allows HPWH performance adjustment when installed in confined space per RESNET HERS Addendum 77. When `extension/HPWHInConfinedSpaceWithoutMitigation` is "true", `extension/HPWHContainmentVolume` is used to calculate the adjustment.
  - Improves HPWH tank volume defaulting, particularly when `NumberofResidents` is provided.
  - Improves electric water heater tank losses when using `EnergyFactor` as the metric; now consistent with how `UniformEnergyFactor` is handled.
- Updated site defaults:
  - `Address/CityMunicipality`, `Address/StateCode`, `GeoLocation/Latitude`, `GeoLocation/Longitude`, and `TimeZone/UTCOffset` now default based on zip code if available.
  - `TimeZone/DSTObserved` now defaults to false if `Address/StateCode` is 'AZ' or 'HI'.
- Minor PV improvements:
  - Allow `PVSystem/AttachedToInverter` to be omitted (unless there are multiple `Inverter` elements).
  - Allow multiple inverters with different efficiencies and use a weighted-average efficiency in the model (previously threw an error)
- For storm windows, removes minimum base window U-factor limit and throws a warning instead if the base window U-factor is below 0.3.
- Whole SFA/MF buildings:
  - Allows modeling inter-unit heat transfer using the `@sameas` attribute.
  - Allows modeling detailed electric vehicles.
  - Documents a workaround for modeling common spaces (conditioned or unconditioned).
  - See the [documentation](https://openstudio-hpxml.readthedocs.io/en/latest/workflow_inputs.html#whole-sfa-mf-buildings) for more information.
- Updated default utility bill rates per EIA energy cost data for 2023.
- Adds "Electric Panel Load: Max Current Rating (A)" output to results_panel.csv.
- Adds error-checking for when the sum of supply/return duct leakage to outside values is too high.
- Adds error-checking for when `HeatPump/HeatingCapacity17F` is provided but `HeatPump/HeatingCapacity` is not.

__Bugfixes__
- Fixes incorrect cooling design conditions when using TMYx weather files (OpenStudio bug).
- Fixes ground-source heat pump plant loop fluid type (OpenStudio bug).
- Fixes HERS sizing methodology when compressor lockout temperature is above the heating design temperature.
- Fixes default hours driven per week for electric vehicles (8.88 -> 9.5).
- Fixes empty TimeDST/TimeUTC columns in JSON timeseries data.
- Fixes an EMS bug in heat pump defrost models that over-estimates defrost fractions.
- Fixes zero mech vent fan energy when CFIS system w/ `AdditionalRuntimeOperatingMode="air handler fan"` has the airflow rate set to zero.
- Fixes requested EnergyPlus timeseries output variables/meters not displayed in DView if they don't have units.
- Fixes possible errors when small water flow rates for variable-speed experimental ground-source heat pump model.
- Fixes possible ground-source heat pump sizing error if the heating or cooling design temperature differences are zero.
- Fixes EMS discharge power program and assignment of default discharging schedule for detailed electric vehicles.
- Avoids thin interior/exterior roof construction layers to help prevent attic temperature out of bounds errors.
