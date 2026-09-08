import sys
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from migrate_csv import (  # noqa: E402
    update_air_leakage_v110_to_v112,
    update_geomtry_unit_v110_to_v112,
    update_geometry_attic_v110_to_v112,
    update_geometry_foundation_v110_to_v112,
)
from read_option_tsv import get_option_names, get_tsv_data  # noqa: E402


def _get_measure_argument_v110(argument_name, measure_path=None):
    """Extract the full argument definition from the measure XML for a given argument name."""
    measure_path = measure_path or (REPO_ROOT / "tests" / "ressource" / "measure.xml")
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


class TestMigrateCsvLeakage(unittest.TestCase):
    def test_air_leakage_from_measure_choices_with_fixed_values(self):
        """Validate legacy leakage inputs map to valid enclosure_air_leakage options."""
        units_choices = _get_measure_choices("air_leakage_units")
        self.assertGreater(
            len(units_choices), 0, "No air_leakage_units choices found in measure.xml."
        )

        # air_leakage_house_pressure is a Double in measure.xml (no explicit choices).
        measure_path = REPO_ROOT / "tests" / "ressource" / "measure.xml"
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

        # for debugging, print the input and output DataFrames
        print("Input DataFrame:")
        print(input_df)
        print("Output DataFrame:")
        print(out_df)

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


class TestMigrateCsvGeometry(unittest.TestCase):
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
        out_df = update_geomtry_unit_v110_to_v112(input_df.copy())

        for idx, exp in enumerate(expected):
            with self.subTest(i=idx, legacy=input_df.loc[idx, "geometry_unit_type"]):
                got = out_df.loc[idx, "geometry_unit_type"]
                self.assertEqual(exp, got)
                self.assertIn(got, valid_option_names)


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
        out_df = update_geometry_attic_v110_to_v112(input_df.copy())

        for idx, exp in enumerate(expected):
            with self.subTest(i=idx, legacy=input_df.loc[idx, "geometry_attic_type"]):
                got = out_df.loc[idx, "geometry_attic_type"]
                self.assertEqual(exp, got)
                self.assertIn(got, valid_option_names)


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
        out_df = update_geometry_foundation_v110_to_v112(input_df.copy())

        # for debugging, print the input and output DataFrames
        print("Input DataFrame:")
        print(input_df)
        print("Output DataFrame:")
        print(out_df)

        for idx, exp in enumerate(expected):
            with self.subTest(
                i=idx, legacy=input_df.loc[idx, "geometry_foundation_type"]
            ):
                got = out_df.loc[idx, "geometry_foundation_type"]
                self.assertEqual(exp, got)
                self.assertIn(got, valid_option_names)


if __name__ == "__main__":
    unittest.main()
