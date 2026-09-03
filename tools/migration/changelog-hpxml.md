# HPXML v5.0 Migration Guide

> ⚠️ **Major Breaking Release**  
> Every document must move to the new namespace `http://hpxmlonline.com/2025/12` and declare SchemaVersion 5.0; the 4.x versions are no longer valid values.

No changes since v5.0-rc2. Here are the total changes since v4.2.

---

## 🛠️ Breaking Changes

### 1. Namespace and Schema Version
- **Old namespace**: `http://hpxmlonline.com/2023/09`
- **New namespace**: `http://hpxmlonline.com/2025/12`
- **Schema Version**: Only 5.0 is now accepted (4.0, 4.1, and 4.2 were removed)

### 2. Replace "none" with "not present" (#451)

Absence of a component is now expressed consistently. The `none` choice was removed from:

- `Wall/Siding`
- `Wall/InteriorFinish/Type`
- `Floor/FloorCovering`
- `Window/InteriorShading/Type`
- `Window/ExteriorShading/Type`
- `BellyAndWing/BellyWrapCondition`
- `Pool/Type`
- `Pool/FilterType`
- `Pool/Pumps/Pump/Type`
- `Pool/Cleaner/Type`
- `Pool/Heater/Type`

**Related changes**:
- `Insulation/None` element → `Insulation/NotPresent`
- `Refrigerator/Type`: `uncategorized` → `other`
- `Skylight/SolarTube` boolean → `Skylight/Type` (fixed, venting, tubular, dome, ...)

### 3. Cool Roofs (#462, #479)

- `cool roof` was removed from `Roof/RoofType`
- Use new `Roof/CoolRoof` boolean instead
- Allows roofing material to be described separately

### 4. Required Units/Value (#467)

`Units` and `Value` are now required when their parent element is present for:
- `AirInfiltrationMeasurement/BuildingAirLeakage`
- `DuctLeakageMeasurement/DuctLeakage`
- `Attic/VentilationRate`
- `Foundation/VentilationRate`
- `Vehicle/FuelEconomyCombined`, `/FuelEconomyCity`, `/FuelEconomyHighway`

---

## ✨ New Elements

- **`Roof/CoolRoof`** (#462)
- **`WaterFixture/Location`** (#463)
  - Choices: bathroom, kitchen, garage, basement, laundry room, outside, other
- **`AirInfiltrationMeasurement/SpecificLeakageArea`** (#455)
- **`Type` attribute** for previously untyped components (#451)
  - Freezer, CookingRange, Oven
  - Window/WindowFilm, Window/InsectScreen, Window/StormWindow
  - Skylight, PVSystem, ElectricVehicleCharger, WindTurbine, CeilingFan
  - PortableElectricSpa

---

## 📋 New and Corrected Choices

| Element | Changes |
|---------|---------|
| `WallAndRoofColor` | Added: white (#465), medium light (#457) |
| `Siding` | Added: stone veneer (#458) |
| `WaterFixtureType` | Added: toilet (#480) |
| `GreenBuildingVerification/Type` | Added: DOE Efficient New Home (#452) |
| `ElectricPanel/HeadroomSpaces` | Can now be negative (#456) |
| Heat pump water heater | Fixed OperatingMode and Voltage enumerations (#466) |

---

## 📝 What's Changed

### Breaking Changes (🛠️)
- #451: Add not present/other/unknown choices
- #462: CoolRoof element
- #467: Require units/value with parent element

### Features & Enhancements
- #452: Add DENH (DOE Efficient New Home) enum
- #455: Add SpecificLeakageArea infiltration element
- #456: Allow ElectricPanel/HeadroomSpaces to be negative
- #457: Allow medium light for wall/roof color
- #458: Allow stone veneer for wall siding
- #463: WaterFixture/Location element
- #465: Add "white" option for roof/wall colors
- #466: Fix HPWH enumerations
- #480: Add "toilet" as a choice for WaterFixtureType

### Maintenance
- #473: Updating github actions versions
- #475: Update to NLR
- #479: Clarify CoolRoof definition
