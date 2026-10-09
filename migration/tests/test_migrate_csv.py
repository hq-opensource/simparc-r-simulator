import subprocess
import sys
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
TESTS_DIR = Path(__file__).resolve().parent

from migration.src.migrate_csv import (
    update_air_leakage_v110_to_v112,
    update_duct_leakage_v110_to_v112,
    update_enclosure_ceiling_v110_to_v112,
    update_enclosure_foundation_wall_v110_to_v112,
    update_enclosure_skylight_v110_to_v112,
    update_enclosure_floor_over_foundation_v110_to_v112,
    update_enclosure_floor_over_garage_v110_to_v112,
    update_enclosure_slab_v110_to_v112,
    update_enclosure_window_v110_to_v112,
    update_enclosure_wall_v110_to_v112,
    update_geometry_average_ceiling_height_v110_to_v112,
    update_geometry_building_num_units_v110_to_v112,
    update_enclosure_overhangs_v110_to_v112,
    update_geometry_skylight_areas_v110_to_v112,
    update_geometry_window_areas_or_wwrs_v110_to_v112,
    update_geometry_unit_cfa_v110_to_v112,
    update_geometry_unit_orientation_v110_to_v112,
    update_geometry_unit_v110_to_v112,
    update_geometry_attic_v110_to_v112,
    update_geometry_foundation_v110_to_v112,
    update_dhw_water_heater_v110_to_v112,
    update_heat_pump_v110_to_v112,
    update_pool_parameters_v110_to_v112,
    update_ventilation_v110_to_v112,
    update_window_interior_shading_v110_to_v112,
    update_simulation_control_daylight_saving_enabled_v110_to_v112,
    update_site_time_zone_utc_offset_v110_to_v112,
    update_year_built_v110_to_v112,
)
from migration.src.utils.utils import _match_enclosure_option  # noqa: E402
from migration.src.utils.read_option_tsv import get_option_names, get_tsv_data  # noqa: E402


def test_option_tsv_paths_resolve_under_repo_root():
    """The migration tool must read TSV files from the repository root, not from migration/src."""
    path = REPO_ROOT / "OpenStudio-HPXML" / "BuildResidentialHPXML" / "resources" / "options" / "enclosure_air_leakage.tsv"
    assert path.exists(), f"Expected TSV file to exist at {path}"
    assert len(get_option_names(str(path))) > 0

def test_migrate_csv_direct_script_execution_has_repo_root_on_path():
    """Running the script directly should work from the repo root without needing package installation."""
    script_path = REPO_ROOT / "migration" / "src" / "migrate_csv.py"
    result = subprocess.run(
        [sys.executable, str(script_path), "--help"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout

def _get_measure_argument_v110(argument_name, measure_path=None):
    """Extract the full argument definition from the measure XML for a given argument name."""
    measure_path = measure_path or (TESTS_DIR / "ressource" / "measure_1.10.xml")
    root = ET.parse(measure_path).getroot()

    for arg in root.findall(".//argument"):
        name_node = arg.find("name")
        if name_node is None:
            continue
        if (name_node.text or "").strip() != argument_name:
            continue

        choices = []
        for choice in arg.findall("./choices/choice"):
            value_node = choice.find("value")
            if value_node is None:
                continue
            val = (value_node.text or "").strip()
            if val:
                choices.append(val)

        default_node = arg.find("default_value")
        required_node = arg.find("required")
        type_node = arg.find("type")

        return {
            "Name": (name_node.text or "").strip(),
            "Type": (type_node.text or "").strip() if type_node is not None else "",
            "Required": (required_node.text or "").strip() if required_node is not None else "",
            "Choices": choices,
            "Default Value": (default_node.text or "").strip() if default_node is not None else "",
        }

    return {}

def _get_measure_choices(argument_name, measure_path=None):
    """Extract measure choices from tests/ressource/measure.xml by argument name."""
    return _get_measure_argument_v110(argument_name, measure_path).get("Choices", [])


def _get_option_row(tsv_path, option_name):
    """Return the TSV row for a specific option name."""
    for row in get_tsv_data(str(tsv_path)):
        if str(row.get("Option Name", "")).strip() == option_name:
            return row
    raise AssertionError(f"Could not find option '{option_name}' in {tsv_path}")

def _print_debug_info(input_df, out_df):
    print("Input DataFrame:")
    print(input_df)
    print("Output DataFrame:")
    print(out_df)

def _assert_option_mapping(self, mapper, input_df, expected, valid_option_names, output_col):
    """Apply a mapper and validate that each legacy value resolves to an option name."""
    out_df = mapper(input_df.copy())
    _print_debug_info(input_df, out_df)
    for idx, exp in enumerate(expected):
        with self.subTest(i=idx, legacy=input_df.iloc[idx].to_dict()):
            got = out_df.iloc[idx][output_col]
            self.assertEqual(exp, got)
            self.assertIn(got, valid_option_names)

class TestMigrateCsvLeakage(unittest.TestCase):
    def test_air_leakage_from_measure_choices_with_fixed_values(self):
        """Validate legacy leakage inputs map to valid enclosure_air_leakage options."""
        units_choices = _get_measure_choices("air_leakage_units")
        self.assertGreater(
            len(units_choices), 0, "No air_leakage_units choices found in measure.xml."
        )

        # air_leakage_house_pressure is a Double in measure.xml (no explicit choices).
        measure_path = TESTS_DIR / "ressource" / "measure_1.10.xml"
        root = ET.parse(measure_path).getroot()
        pressure_arg = None
        for arg in root.findall(".//argument"):
            name_node = arg.find("name")
            if (
                name_node is not None
                and (name_node.text or "").strip() == "air_leakage_house_pressure"
            ):
                pressure_arg = arg
                break
        self.assertIsNotNone(
            pressure_arg,
            "air_leakage_house_pressure argument not found in measure.xml.",
        )

        fixed_values = [1, 3, 0.5, 0.4]
        default_pressure = "50"

        option_tsv_path = (
            REPO_ROOT
            / "OpenStudio-HPXML"
            / "BuildResidentialHPXML"
            / "resources"
            / "options"
            / "enclosure_air_leakage.tsv"
        )
        valid_option_names = set(get_option_names(str(option_tsv_path)))

        test_rows = []
        expected_is_supported = []

        for unit in units_choices:
            for value in fixed_values:
                unit_lower = str(unit).lower()
                if unit_lower == "ach":
                    pressure = default_pressure
                    supported = True
                elif unit_lower == "cfm":
                    # Current migrate_csv behavior doesn't map CFM values to a canonical option.
                    pressure = default_pressure
                    supported = False
                elif unit_lower in {"achnatural", "cfmnatural"}:
                    pressure = ""
                    supported = True
                else:
                    # EffectiveLeakageArea is intentionally unsupported by migrate_csv mapping.
                    pressure = ""
                    supported = False

                test_rows.append(
                    {
                        "air_leakage_value": str(value),
                        "air_leakage_units": unit,
                        "air_leakage_house_pressure": pressure,
                    }
                )
                expected_is_supported.append(supported)

        self.assertGreater(
            len(test_rows), 0, "No leakage test rows built from measure.xml choices."
        )

        input_df = pd.DataFrame(test_rows, dtype=str)
        out_df = update_air_leakage_v110_to_v112(input_df.copy())

        self.assertIn("enclosure_air_leakage", out_df.columns)

        for idx, supported in enumerate(expected_is_supported):
            with self.subTest(
                i=idx,
                unit=test_rows[idx]["air_leakage_units"],
                value=test_rows[idx]["air_leakage_value"],
            ):
                got = out_df.loc[idx, "enclosure_air_leakage"]
                if supported:
                    self.assertIn(got, valid_option_names)
                else:
                    self.assertTrue(pd.isna(got))


class TestMigrateCsvHeatPump(unittest.TestCase):
    def test_heat_pump_legacy_fields_map_to_v112_option_strings(self):
        input_df = pd.DataFrame(
            [
                {
                    "heat_pump_type": "air-to-air",
                    "heat_pump_heating_efficiency_type": "HSPF2",
                    "heat_pump_heating_efficiency": 5.8,
                    "heat_pump_cooling_efficiency_type": "SEER2",
                    "heat_pump_cooling_efficiency": 9.5,
                    "heat_pump_cooling_compressor_type": "single stage",
                    "heat_pump_fraction_heat_load_served": 0.75,
                    "heat_pump_fraction_cool_load_served": 0.75,
                    "heat_pump_compressor_lockout_temp": 5,
                    "heat_pump_backup_type": "integrated",
                    "heat_pump_backup_fuel": "electricity",
                    "heat_pump_backup_heating_efficiency": 1,
                }
            ],
            dtype=str,
        )

        option_tsv = (
            REPO_ROOT
            / "OpenStudio-HPXML"
            / "BuildResidentialHPXML"
            / "resources"
            / "options"
            / "hvac_heat_pump.tsv"
        )
        valid_hvac_heat_pump = set(get_option_names(str(option_tsv)))

        out_df = update_heat_pump_v110_to_v112(input_df.copy())

        self.assertIn("hvac_heat_pump", out_df.columns)
        self.assertIn("hvac_heat_pump_heating_load_served", out_df.columns)
        self.assertIn("hvac_heat_pump_cooling_load_served", out_df.columns)
        self.assertIn("hvac_heat_pump_temperatures", out_df.columns)
        self.assertIn("hvac_heat_pump_backup", out_df.columns)

        self.assertIn(out_df.iloc[0]["hvac_heat_pump"], valid_hvac_heat_pump)
        self.assertEqual(out_df.iloc[0]["hvac_heat_pump_heating_load_served"], "75%")
        self.assertEqual(out_df.iloc[0]["hvac_heat_pump_cooling_load_served"], "75%")
        self.assertEqual(out_df.iloc[0]["hvac_heat_pump_temperatures"], "5F Min Compressor Temp")
        self.assertEqual(
            out_df.iloc[0]["hvac_heat_pump_backup"],
            "Integrated, Electricity, 100% Efficiency",
        )


class TestMigrateCsvGeometry(unittest.TestCase):
    def test_first_five_columns_map_to_v112_schema(self):
        input_df = pd.DataFrame(
            [
                {
                    "simulation_control_daylight_saving_enabled": "false",
                    "site_time_zone_utc_offset": "-7",
                    "geometry_building_num_units": "3",
                    "geometry_average_ceiling_height": "8.24",
                    "geometry_unit_orientation": "95",
                }
            ],
            dtype=str,
        )

        out_df = update_simulation_control_daylight_saving_enabled_v110_to_v112(input_df.copy())
        out_df = update_site_time_zone_utc_offset_v110_to_v112(out_df)
        out_df = update_geometry_building_num_units_v110_to_v112(out_df)
        out_df = update_geometry_average_ceiling_height_v110_to_v112(out_df)
        out_df = update_geometry_unit_orientation_v110_to_v112(out_df)

        self.assertNotIn("simulation_control_daylight_saving_enabled", out_df.columns)
        self.assertNotIn("site_time_zone_utc_offset", out_df.columns)
        self.assertIn("geometry_building_num_units", out_df.columns)
        self.assertEqual(out_df.loc[0, "geometry_building_num_units"], "3")
        self.assertNotIn("geometry_average_ceiling_height", out_df.columns)
        self.assertNotIn("geometry_unit_orientation", out_df.columns)
        self.assertEqual(out_df.loc[0, "geometry_ceiling_height"], "8.0 ft")
        self.assertEqual(out_df.loc[0, "geometry_unit_direction"], "East")

    def test_year_built_and_unit_cfa_are_renamed_to_v112_fields(self):
        input_df = pd.DataFrame(
            [
                {
                    "year_built": "1984",
                    "geometry_unit_cfa": "1450",
                }
            ],
            dtype=str,
        )

        out_df = update_year_built_v110_to_v112(input_df.copy())
        out_df = update_geometry_unit_cfa_v110_to_v112(out_df)

        self.assertNotIn("year_built", out_df.columns)
        self.assertNotIn("geometry_unit_cfa", out_df.columns)
        self.assertEqual(out_df.loc[0, "building_year_built"], "1984")
        self.assertEqual(out_df.loc[0, "geometry_unit_conditioned_floor_area"], "1450")

    def test_window_skylight_and_shading_fields_map_to_v112_option_names(self):
        window_tsv = (
            REPO_ROOT
            / "OpenStudio-HPXML"
            / "BuildResidentialHPXML"
            / "resources"
            / "options"
            / "enclosure_window.tsv"
        )
        skylight_tsv = (
            REPO_ROOT
            / "OpenStudio-HPXML"
            / "BuildResidentialHPXML"
            / "resources"
            / "options"
            / "enclosure_skylight.tsv"
        )
        shading_tsv = (
            REPO_ROOT
            / "OpenStudio-HPXML"
            / "BuildResidentialHPXML"
            / "resources"
            / "options"
            / "enclosure_window_interior_shading.tsv"
        )

        window_row = _get_option_row(window_tsv, "Double, Low-E, Non-Metal, Air, Low Gain")
        skylight_row = _get_option_row(skylight_tsv, "Double, Low-E, Non-Metal, Low Gain")
        shading_row = _get_option_row(shading_tsv, "Summer 0.7, Winter 0.8")

        window_df = pd.DataFrame(
            [
                {
                    "window_ufactor": str(window_row["U-Factor [Btu/hr-ft2-F]"]),
                    "window_shgc": str(window_row["SHGC"]),
                }
            ],
            dtype=str,
        )
        skylight_df = pd.DataFrame(
            [
                {
                    "skylight_ufactor": str(skylight_row["U-Factor [Btu/hr-ft2-F]"]),
                    "skylight_shgc": str(skylight_row["SHGC"]),
                }
            ],
            dtype=str,
        )
        shading_df = pd.DataFrame(
            [
                {
                    "window_interior_shading_summer": str(shading_row["Summer Coefficient [frac]"]),
                    "window_interior_shading_winter": str(shading_row["Winter Coefficient [frac]"]),
                }
            ],
            dtype=str,
        )

        window_out = update_enclosure_window_v110_to_v112(window_df.copy())
        skylight_out = update_enclosure_skylight_v110_to_v112(skylight_df.copy())
        shading_out = update_window_interior_shading_v110_to_v112(shading_df.copy())

        self.assertEqual(window_out.iloc[0]["enclosure_window"], "Double, Low-E, Non-Metal, Air, Low Gain")
        self.assertEqual(skylight_out.iloc[0]["enclosure_skylight"], "Double, Low-E, Non-Metal, Low Gain")
        self.assertEqual(shading_out.iloc[0]["enclosure_window_interior_shading"], "Summer 0.7, Winter 0.8")

        self.assertNotIn("window_ufactor", window_out.columns)
        self.assertNotIn("window_shgc", window_out.columns)
        self.assertNotIn("skylight_ufactor", skylight_out.columns)
        self.assertNotIn("skylight_shgc", skylight_out.columns)
        self.assertNotIn("window_interior_shading_summer", shading_out.columns)
        self.assertNotIn("window_interior_shading_winter", shading_out.columns)

    def test_window_area_and_skylight_area_fields_map_to_v112_geometry_strings(self):
        input_df = pd.DataFrame(
            [
                {
                    "window_front_wwr": "0.15",
                    "window_back_wwr": "0.15",
                    "window_left_wwr": "0.15",
                    "window_right_wwr": "0.15",
                    "window_area_front": "0",
                    "window_area_back": "0",
                    "window_area_left": "0",
                    "window_area_right": "0",
                    "window_aspect_ratio": "1.333",
                    "skylight_area_front": "0",
                    "skylight_area_back": "0",
                    "skylight_area_left": "0",
                    "skylight_area_right": "0",
                },
                {
                    "window_front_wwr": "0",
                    "window_back_wwr": "0",
                    "window_left_wwr": "0",
                    "window_right_wwr": "0",
                    "window_area_front": "108",
                    "window_area_back": "108",
                    "window_area_left": "72",
                    "window_area_right": "72",
                    "window_aspect_ratio": "1.6",
                    "skylight_area_front": "50",
                    "skylight_area_back": "10",
                    "skylight_area_left": "0",
                    "skylight_area_right": "25",
                },
            ],
            dtype=str,
        )

        out_df = update_geometry_window_areas_or_wwrs_v110_to_v112(input_df.copy())
        out_df = update_geometry_skylight_areas_v110_to_v112(out_df)

        self.assertEqual(out_df.loc[0, "geometry_window_areas_or_wwrs"], "0.15, 0.15, 0.15, 0.15")
        self.assertEqual(out_df.loc[1, "geometry_window_areas_or_wwrs"], "108, 108, 72, 72")
        self.assertEqual(out_df.loc[0, "geometry_skylight_areas"], "0, 0, 0, 0")
        self.assertEqual(out_df.loc[1, "geometry_skylight_areas"], "50, 10, 0, 25")

        for col in [
            "window_front_wwr",
            "window_back_wwr",
            "window_left_wwr",
            "window_right_wwr",
            "window_area_front",
            "window_area_back",
            "window_area_left",
            "window_area_right",
            "window_aspect_ratio",
            "skylight_area_front",
            "skylight_area_back",
            "skylight_area_left",
            "skylight_area_right",
        ]:
            self.assertNotIn(col, out_df.columns)

    def test_approximate_matches_emit_explicit_warnings(self):
        """Validate that approximate matchers log when they select a nearby option."""
        with self.assertLogs("migration.src.utils.utils", level="WARNING") as logs:
            matched = _match_enclosure_option("0.73 ACH50", ["0.5 ACH50", "1.0 ACH50"])

        self.assertEqual(matched, "0.5 ACH50")
        self.assertTrue(
            any("Approximated enclosure_air_leakage value" in message for message in logs.output),
            logs.output,
        )

        window_df = pd.DataFrame(
            [
                {
                    "window_ufactor": "0.3333",
                    "window_shgc": "0.2718",
                }
            ],
            dtype=str,
        )

        with self.assertLogs("migration.src.utils.utils", level="WARNING") as logs:
            window_out = update_enclosure_window_v110_to_v112(window_df.copy())

        self.assertIn("enclosure_window", window_out.columns)
        self.assertTrue(
            any("Approximated enclosure_window.tsv option" in message for message in logs.output),
            logs.output,
        )

        floor_foundation_df = pd.DataFrame(
            [
                {
                    "floor_over_foundation_assembly_r": "0.0",
                }
                ,
                {
                    "floor_over_foundation_assembly_r": "0.0",
                },
                {
                    "floor_over_foundation_assembly_r": "0.0",
                },
            ],
            dtype=str,
        )

        with self.assertLogs("migration.src.utils.utils", level="WARNING") as logs:
            floor_foundation_out = update_enclosure_floor_over_foundation_v110_to_v112(
                floor_foundation_df.copy()
            )

        self.assertIn("enclosure_floor_over_foundation", floor_foundation_out.columns)
        self.assertTrue(
            any(" : WoodFrame 2.16\n  target values:\n    Assembly R-Value [F-ft2-hr/Btu]: 0.0" in message for message in logs.output),
            logs.output,
        )
        self.assertEqual(
            sum(" : WoodFrame 2.16\n  target values:\n    Assembly R-Value [F-ft2-hr/Btu]: 0.0" in message for message in logs.output),
            1,
            logs.output,
        )

        foundation_wall_df = pd.DataFrame(
            [
                {
                    "foundation_wall_type": "solid concrete",
                    "foundation_wall_insulation_r": "10.05",
                    "foundation_wall_insulation_location": "interior",
                    "foundation_wall_insulation_distance_to_top": "",
                },
                {
                    "foundation_wall_type": "solid concrete",
                    "foundation_wall_insulation_r": "10.05",
                    "foundation_wall_insulation_location": "interior",
                    "foundation_wall_insulation_distance_to_top": "",
                },
                {
                    "foundation_wall_type": "solid concrete",
                    "foundation_wall_insulation_r": "10.05",
                    "foundation_wall_insulation_location": "interior",
                    "foundation_wall_insulation_distance_to_top": "",
                }
            ],
            dtype=str,
        )

        with self.assertLogs("migration.src.utils.utils", level="WARNING") as logs:
            foundation_wall_out = update_enclosure_foundation_wall_v110_to_v112(
                foundation_wall_df.copy()
            )

        self.assertIn("enclosure_foundation_wall", foundation_wall_out.columns)
        self.assertTrue(
            any("Approximated enclosure_foundation_wall.tsv option" in message for message in logs.output),
            logs.output,
        )
        self.assertTrue(
            any("10.1" in message for message in logs.output),
            logs.output,
        )
        self.assertEqual(
            sum("Approximated enclosure_foundation_wall.tsv option" in message for message in logs.output),
            1,
            logs.output,
        )

    def test_wall_ceiling_and_floor_assembly_fields_map_to_v112_option_names(self):
        wall_tsv = (
            REPO_ROOT
            / "OpenStudio-HPXML"
            / "BuildResidentialHPXML"
            / "resources"
            / "options"
            / "enclosure_wall.tsv"
        )
        ceiling_tsv = (
            REPO_ROOT
            / "OpenStudio-HPXML"
            / "BuildResidentialHPXML"
            / "resources"
            / "options"
            / "enclosure_ceiling.tsv"
        )
        floor_foundation_tsv = (
            REPO_ROOT
            / "OpenStudio-HPXML"
            / "BuildResidentialHPXML"
            / "resources"
            / "options"
            / "enclosure_floor_over_foundation.tsv"
        )
        floor_garage_tsv = (
            REPO_ROOT
            / "OpenStudio-HPXML"
            / "BuildResidentialHPXML"
            / "resources"
            / "options"
            / "enclosure_floor_over_garage.tsv"
        )

        wall_row = _get_option_row(wall_tsv, "Wood Stud, R-13")
        ceiling_row = _get_option_row(ceiling_tsv, "R-13")
        floor_foundation_row = _get_option_row(floor_foundation_tsv, "Wood Frame, R-13")
        floor_garage_row = _get_option_row(floor_garage_tsv, "Wood Frame, R-13")

        input_df = pd.DataFrame(
            [
                {
                    "wall_type": "WoodStud",
                    "wall_assembly_r": str(wall_row["Assembly R-Value [F-ft2-hr/Btu]"]),
                    "ceiling_assembly_r": str(ceiling_row["Assembly R-Value [F-ft2-hr/Btu]"]),
                    "floor_over_foundation_assembly_r": str(
                        floor_foundation_row["Assembly R-Value [F-ft2-hr/Btu]"]
                    ),
                    "floor_over_garage_assembly_r": str(
                        floor_garage_row["Assembly R-Value [F-ft2-hr/Btu]"]
                    ),
                }
            ],
            dtype=str,
        )

        out_df = update_enclosure_wall_v110_to_v112(input_df.copy())
        out_df = update_enclosure_ceiling_v110_to_v112(out_df)
        out_df = update_enclosure_floor_over_foundation_v110_to_v112(out_df)
        out_df = update_enclosure_floor_over_garage_v110_to_v112(out_df)

        self.assertEqual(out_df.loc[0, "enclosure_wall"], "Wood Stud, R-13")
        self.assertEqual(out_df.loc[0, "enclosure_ceiling"], "R-13")
        self.assertEqual(out_df.loc[0, "enclosure_floor_over_foundation"], "Wood Frame, R-13")
        self.assertEqual(out_df.loc[0, "enclosure_floor_over_garage"], "Wood Frame, R-13")

        self.assertNotIn("wall_type", out_df.columns)
        self.assertNotIn("wall_assembly_r", out_df.columns)
        self.assertNotIn("ceiling_assembly_r", out_df.columns)
        self.assertNotIn("floor_over_foundation_assembly_r", out_df.columns)
        self.assertNotIn("floor_over_garage_assembly_r", out_df.columns)

    def test_all_geometry_unit_type_from_legacy_map_to_option_name(self):
        """Validate legacy measure.xml geometry_unit_type choices map to geometry_unit_type Option Name values."""
        constraints = {"geometry_unit_type": _get_measure_argument_v110("geometry_unit_type")}
        unit_choices = constraints["geometry_unit_type"].get("Choices", [])
        self.assertGreater(
            len(unit_choices), 0, "No geometry_unit_type choices found in measure.xml."
        )

        tsv_path = (
            REPO_ROOT
            / "OpenStudio-HPXML"
            / "BuildResidentialHPXML"
            / "resources"
            / "options"
            / "geometry_unit_type.tsv"
        )
        rows = get_tsv_data(str(tsv_path))

        options_by_unit = {}
        valid_option_names = set()
        for row in rows:
            option_name = str(row.get("Option Name", "")).strip()
            if option_name == "" or option_name.startswith("#"):
                continue
            unit_type = str(row.get("Facility Type", "")).strip()
            stories = row.get("Number of Stories", "")
            if unit_type == "" or stories == "":
                continue
            options_by_unit.setdefault(unit_type.lower(), []).append(
                (str(stories), option_name)
            )
            valid_option_names.add(option_name)

        test_rows = []
        expected = []
        covered_unit_choices = set()

        for unit_type in unit_choices:
            unit_key = str(unit_type).strip().lower()
            unit_candidates = options_by_unit.get(unit_key, [])
            if len(unit_candidates) == 0:
                continue

            covered_unit_choices.add(unit_key)
            for stories, option_name in unit_candidates:
                test_rows.append(
                    {
                        "geometry_unit_type": unit_type,
                        "geometry_unit_num_floors_above_grade": stories,
                    }
                )
                expected.append(option_name)

        self.assertGreater(
            len(test_rows),
            0,
            "No geometry unit test rows built from measure.xml choices.",
        )
        self.assertEqual(set(c.lower() for c in unit_choices), covered_unit_choices)

        input_df = pd.DataFrame(test_rows, dtype=str)
        _assert_option_mapping(
            self,
            update_geometry_unit_v110_to_v112,
            input_df,
            expected,
            valid_option_names,
            "geometry_unit_type",
        )


class TestMigrateCsvAttic(unittest.TestCase):
    def test_all_attic_type_from_legacy_map_to_option_name(self):
        """Validate legacy measure.xml attic/roof choices map to canonical Option Name values."""
        constraints = {
            "geometry_attic_type": _get_measure_argument_v110("geometry_attic_type"),
            "geometry_roof_type": _get_measure_argument_v110("geometry_roof_type"),
        }
        attic_choices = constraints["geometry_attic_type"].get("Choices", [])
        roof_choices = constraints["geometry_roof_type"].get("Choices", [])

        self.assertGreater(
            len(attic_choices),
            0,
            "No geometry_attic_type choices found in measure.xml.",
        )
        self.assertGreater(
            len(roof_choices), 0, "No geometry_roof_type choices found in measure.xml."
        )

        tsv_path = (
            REPO_ROOT
            / "OpenStudio-HPXML"
            / "BuildResidentialHPXML"
            / "resources"
            / "options"
            / "geometry_attic_type.tsv"
        )
        rows = get_tsv_data(str(tsv_path))

        direct_lookup = {}
        options_by_attic = {}
        valid_option_names = set()
        for row in rows:
            option_name = str(row.get("Option Name", "")).strip()
            if option_name == "" or option_name.startswith("#"):
                continue

            attic_type = str(row.get("Attic Type", "")).strip()
            roof_type = str(row.get("Roof Type", "")).strip()
            if attic_type == "":
                continue

            attic_key = attic_type.lower()
            roof_key = roof_type.lower()
            direct_lookup[(attic_key, roof_key)] = option_name
            options_by_attic.setdefault(attic_key, []).append(option_name)
            valid_option_names.add(option_name)

        test_rows = []
        expected = []
        covered_attic_choices = set()

        for attic_type in attic_choices:
            attic_key = str(attic_type).strip().lower()
            candidates = options_by_attic.get(attic_key, [])
            if len(candidates) == 0:
                continue

            covered_attic_choices.add(attic_key)

            # For attic types with multiple roof-dependent options, test all roof choices.
            if len(set(candidates)) > 1:
                for roof_type in roof_choices:
                    roof_key = str(roof_type).strip().lower()
                    mapped = direct_lookup.get((attic_key, roof_key))
                    if mapped is None:
                        continue
                    test_rows.append(
                        {
                            "geometry_attic_type": attic_type,
                            "geometry_roof_type": roof_type,
                        }
                    )
                    expected.append(mapped)
                continue

            # For single-option attic types (e.g., FlatRoof/BelowApartment), one roof value is sufficient.
            test_rows.append(
                {
                    "geometry_attic_type": attic_type,
                    "geometry_roof_type": roof_choices[0],
                }
            )
            expected.append(candidates[0])

        self.assertGreater(
            len(test_rows), 0, "No test rows built from measure.xml choices."
        )
        self.assertEqual(set(c.lower() for c in attic_choices), covered_attic_choices)

        input_df = pd.DataFrame(test_rows, dtype=str)
        _assert_option_mapping(
            self,
            update_geometry_attic_v110_to_v112,
            input_df,
            expected,
            valid_option_names,
            "geometry_attic_type",
        )


class TestMigrateCsvFoundation(unittest.TestCase):
    def test_all_foundation_type_from_legacy_map_to_option_name(self):
        """Validate legacy measure.xml geometry_foundation_type choices map to geometry_foundation_type Option Name values."""
        constraints = {
            "geometry_foundation_type": _get_measure_argument_v110("geometry_foundation_type"),
        }
        foundation_choices = constraints["geometry_foundation_type"].get("Choices", [])
        self.assertGreater(
            len(foundation_choices),
            0,
            "No geometry_foundation_type choices found in measure.xml.",
        )

        tsv_path = (
            REPO_ROOT
            / "OpenStudio-HPXML"
            / "BuildResidentialHPXML"
            / "resources"
            / "options"
            / "geometry_foundation_type.tsv"
        )
        rows = get_tsv_data(str(tsv_path))

        rows_by_type = {}
        valid_option_names = set()
        for row in rows:
            option_name = str(row.get("Option Name", "")).strip()
            if option_name == "" or option_name.startswith("#"):
                continue
            if option_name.lower().startswith("detailed example:"):
                continue
            if option_name.lower().startswith("ashrae 140 tests:"):
                continue

            type_name = str(row.get("Type", "")).strip()
            height = row.get("Height [ft]", "")
            hag = row.get("Height Above Grade [ft]", "")
            rim_joist = row.get("Rim Joist Height [in]", "")
            if type_name == "":
                continue

            rows_by_type.setdefault(type_name.lower(), []).append(
                (str(hag), str(height), str(rim_joist), option_name)
            )
            valid_option_names.add(option_name)

        test_rows = []
        expected = []
        covered_foundation_choices = set()

        for foundation_type in foundation_choices:
            type_key = str(foundation_type).strip().lower()
            candidates = rows_by_type.get(type_key, [])
            if len(candidates) == 0:
                continue

            covered_foundation_choices.add(type_key)
            for hag, height, rim_joist, option_name in candidates:
                test_rows.append(
                    {
                        "geometry_foundation_type": foundation_type,
                        "geometry_foundation_height_above_grade": hag,
                        "geometry_foundation_height": height,
                        "geometry_rim_joist_height": rim_joist,
                    }
                )
                expected.append(option_name)

        self.assertGreater(
            len(test_rows), 0, "No foundation test rows built from measure.xml choices."
        )
        self.assertEqual(
            set(c.lower() for c in foundation_choices), covered_foundation_choices
        )

        input_df = pd.DataFrame(test_rows, dtype=str)
        _assert_option_mapping(
            self,
            update_geometry_foundation_v110_to_v112,
            input_df,
            expected,
            valid_option_names,
            "geometry_foundation_type",
        )


class TestMigrateCsvOverhangs(unittest.TestCase):
    def test_legacy_overhang_columns_map_to_enclosure_overhangs(self):
        """Validate legacy overhang columns resolve to a v1.12 enclosure_overhangs option."""
        input_df = pd.DataFrame(
            [
                {
                    "overhangs_front_depth": "1",
                    "overhangs_front_distance_to_top_of_window": "1",
                    "overhangs_front_distance_to_bottom_of_window": "4",
                }
            ]
        )

        out_df = update_enclosure_overhangs_v110_to_v112(input_df.copy())
        self.assertEqual(out_df.loc[0, "enclosure_overhangs"], "1ft, All Windows")
        self.assertNotIn("overhangs_front_depth", out_df.columns)
        self.assertNotIn("overhangs_front_distance_to_top_of_window", out_df.columns)
        self.assertNotIn("overhangs_front_distance_to_bottom_of_window", out_df.columns)


class TestMigrateCsvSlab(unittest.TestCase):
    def test_legacy_slab_columns_map_to_enclosure_slab(self):
        """Validate legacy floor_type and slab insulation fields resolve to enclosure_slab."""
        input_df = pd.DataFrame(
            [
                {
                    "floor_type": "WoodFrame",
                    "slab_perimeter_insulation_r": "0",
                    "slab_under_insulation_r": "0",
                },
                {
                    "floor_type": "WoodFrame",
                    "slab_perimeter_insulation_r": "0",
                    "slab_under_insulation_r": "5",
                },
                {
                    "floor_type": "SteelFrame",
                    "slab_perimeter_insulation_r": "5",
                    "slab_under_insulation_r": "0",
                },
                {
                    "floor_type": "WoodFrame",
                    "slab_perimeter_insulation_r": "5",
                    "slab_under_insulation_r": "5",
                },
            ],
            dtype=str,
        )

        out_df = update_enclosure_slab_v110_to_v112(input_df.copy())

        self.assertEqual(out_df.loc[0, "enclosure_slab"], "Uninsulated")
        self.assertEqual(out_df.loc[1, "enclosure_slab"], "Under Slab, 2ft, R-5")
        self.assertEqual(out_df.loc[2, "enclosure_slab"], "Perimeter, 2ft, R-5")
        self.assertEqual(out_df.loc[3, "enclosure_slab"], "Whole Slab, R-5")

        self.assertNotIn("floor_type", out_df.columns)
        self.assertNotIn("slab_perimeter_insulation_r", out_df.columns)
        self.assertNotIn("slab_under_insulation_r", out_df.columns)


class TestMigrateCsvPoolSpa(unittest.TestCase):
    def test_pool_and_spa_legacy_columns_map_to_misc_options(self):
        """Validate pool/spa legacy columns are migrated to misc_pool/misc_permanent_spa."""
        input_df = pd.DataFrame(
            [
                {
                    "pool_present": "false",
                    "pool_pump_usage_multiplier": "",
                    "pool_heater_type": "none",
                    "pool_heater_usage_multiplier": "",
                    "permanent_spa_present": "false",
                    "permanent_spa_heater_type": "none",
                },
                {
                    "pool_present": "true",
                    "pool_pump_usage_multiplier": "0.5",
                    "pool_heater_type": "none",
                    "pool_heater_usage_multiplier": "",
                    "permanent_spa_present": "true",
                    "permanent_spa_heater_type": "electric resistance",
                    "permanent_spa_heater_usage_multiplier": "2",
                },
                {
                    "pool_present": "true",
                    "pool_pump_annual_kwh": "2700",
                    "pool_heater_type": "gas fired",
                    "pool_heater_annual_therm": "500",
                    "permanent_spa_present": "true",
                    "permanent_spa_pump_annual_kwh": "1000",
                    "permanent_spa_heater_type": "heat pump",
                    "permanent_spa_heater_annual_kwh": "260",
                },
            ],
            dtype=str,
        )

        out_df = update_pool_parameters_v110_to_v112(input_df.copy())

        self.assertEqual(out_df.loc[0, "misc_pool"], "None")
        self.assertEqual(out_df.loc[0, "misc_permanent_spa"], "None")

        self.assertEqual(out_df.loc[1, "misc_pool"], "Unheated, 50% Usage")
        self.assertEqual(
            out_df.loc[1, "misc_permanent_spa"],
            "Electric Resistance Heater, 200% Usage",
        )

        self.assertEqual(
            out_df.loc[2, "misc_pool"],
            "Detailed Example: 2700 kWh/yr Pump, 500 therms/yr Natural Gas Heater",
        )
        self.assertEqual(
            out_df.loc[2, "misc_permanent_spa"],
            "Detailed Example: 1000 kWh/yr Pump, 260 kWh/yr Heat Pump Heater",
        )

        dropped_cols = [
            "pool_present",
            "pool_pump_annual_kwh",
            "pool_pump_usage_multiplier",
            "pool_heater_type",
            "pool_heater_annual_kwh",
            "pool_heater_annual_therm",
            "pool_heater_usage_multiplier",
            "permanent_spa_present",
            "permanent_spa_pump_annual_kwh",
            "permanent_spa_pump_usage_multiplier",
            "permanent_spa_heater_type",
            "permanent_spa_heater_annual_kwh",
            "permanent_spa_heater_annual_therm",
            "permanent_spa_heater_usage_multiplier",
        ]
        for col in dropped_cols:
            self.assertNotIn(col, out_df.columns)


class TestMigrateCsvDhwWaterHeater(unittest.TestCase):
    def test_legacy_water_heater_columns_map_to_dhw_water_heater(self):
        """Validate legacy water-heater columns resolve to dhw_water_heater and location."""
        input_df = pd.DataFrame(
            [
                {
                    "water_heater_type": "storage water heater",
                    "water_heater_fuel_type": "electricity",
                    "water_heater_efficiency_type": "EnergyFactor",
                    "water_heater_efficiency": "0.92",
                    "water_heater_recovery_efficiency": "0.0",
                    "water_heater_standby_loss": "0.0",
                    "water_heater_jacket_rvalue": "0.0",
                    "water_heater_setpoint_temperature": "125",
                    "water_heater_location": "conditioned space",
                },
                {
                    "water_heater_type": "storage water heater",
                    "water_heater_fuel_type": "natural gas",
                    "water_heater_efficiency_type": "EnergyFactor",
                    "water_heater_efficiency": "0.59",
                    "water_heater_recovery_efficiency": "0.76",
                    "water_heater_standby_loss": "0.0",
                    "water_heater_jacket_rvalue": "0.0",
                    "water_heater_setpoint_temperature": "125",
                    "water_heater_location": "other multifamily buffer space",
                },
                {
                    "water_heater_type": "storage water heater",
                    "water_heater_fuel_type": "fuel oil",
                    "water_heater_efficiency_type": "EnergyFactor",
                    "water_heater_efficiency": "0.62",
                    "water_heater_recovery_efficiency": "0.78",
                    "water_heater_standby_loss": "0.0",
                    "water_heater_jacket_rvalue": "0.0",
                    "water_heater_setpoint_temperature": "125",
                    "water_heater_location": "conditioned space",
                },
                {
                    "water_heater_type": "instantaneous water heater",
                    "water_heater_fuel_type": "electricity",
                    "water_heater_efficiency_type": "EnergyFactor",
                    "water_heater_efficiency": "0.92",
                    "water_heater_recovery_efficiency": "0.0",
                    "water_heater_standby_loss": "0.0",
                    "water_heater_jacket_rvalue": "0.0",
                    "water_heater_setpoint_temperature": "125",
                    "water_heater_location": "",
                },
            ],
            dtype=str,
        )

        out_df = update_dhw_water_heater_v110_to_v112(input_df.copy())

        self.assertEqual(out_df.loc[0, "dhw_water_heater"], "Electricity, Tank, UEF 0.92")
        self.assertEqual(out_df.loc[0, "dhw_water_heater_location"], "Conditioned Space")

        self.assertEqual(
            out_df.loc[1, "dhw_water_heater"],
            "Detailed Example: Natural Gas, Tank, 50 gal, EF 0.59",
        )
        self.assertEqual(
            out_df.loc[1, "dhw_water_heater_location"],
            "SFA/MF Other Heated Space",
        )

        self.assertEqual(out_df.loc[2, "dhw_water_heater"], "Fuel Oil, Tank, UEF 0.61")
        self.assertEqual(out_df.loc[2, "dhw_water_heater_location"], "Conditioned Space")

        self.assertEqual(out_df.loc[3, "dhw_water_heater"], "Electricity, Tankless, UEF 0.94")
        self.assertEqual(out_df.loc[3, "dhw_water_heater_location"], "Default")

        for col in [
            "water_heater_fuel_type",
            "water_heater_efficiency_type",
            "water_heater_efficiency",
            "water_heater_recovery_efficiency",
            "water_heater_standby_loss",
            "water_heater_jacket_rvalue",
            "water_heater_setpoint_temperature",
            "water_heater_type",
            "water_heater_location",
        ]:
            self.assertNotIn(col, out_df.columns)


class TestMigrateCsvVentilation(unittest.TestCase):
    def test_legacy_ventilation_columns_map_to_v112_options(self):
        """Validate legacy ventilation columns resolve to v1.12 ventilation option strings."""
        input_df = pd.DataFrame(
            [
                {
                    "mech_vent_fan_type": "heat recovery ventilator",
                    "mech_vent_sensible_recovery_efficiency": "0.6",
                    "mech_vent_total_recovery_efficiency": "0.0",
                    "whole_house_fan_present": "False",
                    "whole_house_fan_flow_rate": "0",
                    "whole_house_fan_power": "0",
                    "bathroom_fans_start_hour": "5",
                    "kitchen_fans_start_hour": "17",
                    "window_fraction_operable": "0.67",
                },
                {
                    "mech_vent_fan_type": "energy recovery ventilator",
                    "mech_vent_sensible_recovery_efficiency": "0.85",
                    "mech_vent_total_recovery_efficiency": "0.72",
                    "whole_house_fan_present": "True",
                    "whole_house_fan_flow_rate": "4500",
                    "whole_house_fan_power": "300",
                    "bathroom_fans_start_hour": "7",
                    "kitchen_fans_start_hour": "18",
                    "window_fraction_operable": "0.5",
                },
            ],
            dtype=str,
        )

        out_df = update_ventilation_v110_to_v112(input_df.copy())

        self.assertEqual(out_df.loc[0, "ventilation_mechanical"], "HRV, 60%")
        self.assertEqual(out_df.loc[0, "ventilation_whole_house_fan"], "None")
        self.assertEqual(out_df.loc[0, "ventilation_bathroom"], "Default")
        self.assertEqual(out_df.loc[0, "ventilation_kitchen"], "Default")
        self.assertEqual(out_df.loc[0, "enclosure_window_natural_ventilation"], "67% Operable Windows")

        self.assertEqual(out_df.loc[1, "ventilation_mechanical"], "ERV, 85%")
        self.assertEqual(out_df.loc[1, "ventilation_whole_house_fan"], "Detailed Example: 4500 cfm, 300 W")
        self.assertEqual(out_df.loc[1, "ventilation_bathroom"], "Default")
        self.assertEqual(out_df.loc[1, "ventilation_kitchen"], "Default")
        self.assertEqual(out_df.loc[1, "enclosure_window_natural_ventilation"], "50% Operable Windows")

        for col in [
            "mech_vent_fan_type",
            "mech_vent_flow_rate",
            "mech_vent_hours_in_operation",
            "mech_vent_recovery_efficiency_type",
            "mech_vent_total_recovery_efficiency",
            "mech_vent_sensible_recovery_efficiency",
            "mech_vent_fan_power",
            "mech_vent_num_units_served",
            "whole_house_fan_present",
            "whole_house_fan_flow_rate",
            "whole_house_fan_power",
            "bathroom_fans_start_hour",
            "kitchen_fans_start_hour",
            "window_fraction_operable",
        ]:
            self.assertNotIn(col, out_df.columns)


class TestMigrateCsvDucts(unittest.TestCase):
    def test_legacy_duct_columns_map_to_hvac_ducts(self):
        input_df = pd.DataFrame(
            [
                {
                    "HVAC Has Ducts": "No",
                    "ducts_leakage_units": "Percent",
                    "ducts_supply_leakage_to_outside_value": "0.1",
                    "ducts_return_leakage_to_outside_value": "0.1",
                    "ducts_supply_insulation_r": "0",
                    "ducts_return_insulation_r": "0",
                },
                {
                    "HVAC Has Ducts": "Yes",
                    "ducts_leakage_units": "Percent",
                    "ducts_supply_leakage_to_outside_value": "0.075",
                    "ducts_return_leakage_to_outside_value": "0.075",
                    "ducts_supply_insulation_r": "0",
                    "ducts_return_insulation_r": "0",
                },
                {
                    "HVAC Has Ducts": "Yes",
                    "ducts_leakage_units": "Percent",
                    "ducts_supply_leakage_to_outside_value": "0.05",
                    "ducts_return_leakage_to_outside_value": "0.05",
                    "ducts_supply_insulation_r": "4",
                    "ducts_return_insulation_r": "4",
                },
                {
                    "HVAC Has Ducts": "Yes",
                    "hvac_ducts": "10% Leakage, R-6",
                    "ducts_leakage_units": "Percent",
                    "ducts_supply_leakage_to_outside_value": "0.1",
                    "ducts_return_leakage_to_outside_value": "0.1",
                    "ducts_supply_insulation_r": "6",
                    "ducts_return_insulation_r": "6",
                },
            ],
            dtype=str,
        )

        out_df = update_duct_leakage_v110_to_v112(input_df.copy())

        self.assertEqual(out_df.loc[0, "hvac_ducts"], "None")
        self.assertEqual(out_df.loc[1, "hvac_ducts"], "15% Leakage, Uninsulated")
        self.assertEqual(out_df.loc[2, "hvac_ducts"], "10% Leakage, R-4")
        self.assertEqual(out_df.loc[3, "hvac_ducts"], "10% Leakage, R-6")

        dropped_cols = [
            "ducts_leakage_units",
            "ducts_supply_leakage_to_outside_value",
            "ducts_supply_insulation_r",
            "ducts_return_leakage_to_outside_value",
            "ducts_return_insulation_r",
        ]
        for col in dropped_cols:
            self.assertNotIn(col, out_df.columns)


if __name__ == "__main__":
    unittest.main()
