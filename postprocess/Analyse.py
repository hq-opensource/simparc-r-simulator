import warnings
import pandas as pd
from postprocess.kpi import ParametricKPICalculator

warnings.simplefilter("ignore")

_KBTU_TO_KWH = 0.293071

# ---------------------------------------------------------------------------
# Mapping des colonnes brutes (CSV timeseries apres jointure multi-header dans
# postprocessing.py) vers les noms canoniques utilises par ParametricKPICalculator.
# Source: loaders/loader_simparc.py (SIMPARC_CONFIG["column_mapping"])
# ---------------------------------------------------------------------------
_COLUMN_MAPPING = {
    "Time":                                                             "dateinterval",
    "TimeUTC":                                                          "dateinterval_utc",
    "Weather: Drybulb Temperature_F":                                   "temperatureatmospherique",
    "Energy Use: Total_kBtu":                                           "Energy Use Total",
    "Energy Use: Net_kBtu":                                             "Energy Use Net",
    "Fuel Use: Electricity: Total_kWh":                                 "Fuel Use Electricity Total",
    "Fuel Use: Electricity: Net_kWh":                                   "Fuel Use Electricity Net",
    "Fuel Use: Natural Gas: Total_kBtu":                                "Fuel Use Natural Gas Total",
    "Fuel Use: Natural Gas: Net_kBtu":                                  "Fuel Use Natural Gas Net",
    "Fuel Use: Fuel Oil: Total_kBtu":                                   "Fuel Use Fuel Oil Total",
    "Fuel Use: Fuel Oil: Net_kBtu":                                     "Fuel Use Fuel Oil Net",
    "Fuel Use: Propane: Total_kBtu":                                    "Fuel Use Propane Total",
    "Fuel Use: Propane: Net_kBtu":                                      "Fuel Use Propane Net",
    "Fuel Use: Wood Cord: Total_kBtu":                                  "Fuel Use Wood Cord Total",
    "Fuel Use: Wood Cord: Net_kBtu":                                    "Fuel Use Wood Cord Net",
    "Fuel Use: Wood Pellets: Total_kBtu":                               "Fuel Use Wood Pellets Total",
    "Fuel Use: Wood Pellets: Net_kBtu":                                 "Fuel Use Wood Pellets Net",
    "Fuel Use: Coal: Total_kBtu":                                       "Fuel Use Coal Total",
    "Fuel Use: Coal: Net_kBtu":                                         "Fuel Use Coal Net",
    # End Use electricity (kWh - pas de conversion)
    "End Use: Electricity: Heating_kWh":                                "End Use Electricity Heating",
    "End Use: Electricity: Heating Fans/Pumps_kWh":                     "End Use Electricity Heating FansPumps",
    "End Use: Electricity: Heating Heat Pump Backup_kWh":               "End Use Electricity Heating Heat Pump Backup",
    "End Use: Electricity: Heating Heat Pump Backup Fans/Pumps_kWh":    "End Use Electricity Heating Heat Pump Backup FansPumps",
    "End Use: Electricity: Cooling_kWh":                                "End Use Electricity Cooling",
    "End Use: Electricity: Cooling Fans/Pumps_kWh":                     "End Use Electricity Cooling FansPumps",
    "End Use: Electricity: Hot Water_kWh":                              "End Use Electricity Hot Water",
    "End Use: Electricity: Lighting Interior_kWh":                      "End Use Electricity Lighting Interior",
    "End Use: Electricity: Lighting Exterior_kWh":                      "End Use Electricity Lighting Exterior",
    "End Use: Electricity: Mech Vent_kWh":                              "End Use Electricity Mech Vent",
    "End Use: Electricity: Refrigerator_kWh":                           "End Use Electricity Refrigerator",
    "End Use: Electricity: Freezer_kWh":                                "End Use Electricity Freezer",
    "End Use: Electricity: Dishwasher_kWh":                             "End Use Electricity Dishwasher",
    "End Use: Electricity: Clothes Washer_kWh":                         "End Use Electricity Clothes Washer",
    "End Use: Electricity: Clothes Dryer_kWh":                          "End Use Electricity Clothes Dryer",
    "End Use: Electricity: Range/Oven_kWh":                             "End Use Electricity RangeOven",
    "End Use: Electricity: Ceiling Fan_kWh":                            "End Use Electricity Ceiling Fan",
    "End Use: Electricity: Television_kWh":                             "End Use Electricity Television",
    "End Use: Electricity: Plug Loads_kWh":                             "End Use Electricity Plug Loads",
    "End Use: Electricity: Pool Heater_kWh":                            "End Use Electricity Pool Heater",
    "End Use: Electricity: Pool Pump_kWh":                              "End Use Electricity Pool Pump",
    # End Use gaz naturel (kBtu - conversion en kWh)
    "End Use: Natural Gas: Heating_kBtu":                               "End Use Natural Gas Heating",
    "End Use: Natural Gas: Heating Heat Pump Backup_kBtu":              "End Use Natural Gas Heating Heat Pump Backup",
    "End Use: Natural Gas: Hot Water_kBtu":                             "End Use Natural Gas Hot Water",
    "End Use: Natural Gas: Clothes Dryer_kBtu":                         "End Use Natural Gas Clothes Dryer",
    "End Use: Natural Gas: Range/Oven_kBtu":                            "End Use Natural Gas RangeOven",
    "End Use: Natural Gas: Mech Vent Preheating_kBtu":                  "End Use Natural Gas Mech Vent Preheating",
    "End Use: Natural Gas: Pool Heater_kBtu":                           "End Use Natural Gas Pool Heater",
    "End Use: Natural Gas: Permanent Spa Heater_kBtu":                  "End Use Natural Gas Permanent Spa Heater",
    "End Use: Natural Gas: Grill_kBtu":                                 "End Use Natural Gas Grill",
    "End Use: Natural Gas: Lighting_kBtu":                              "End Use Natural Gas Lighting",
    "End Use: Natural Gas: Fireplace_kBtu":                             "End Use Natural Gas Fireplace",
    "End Use: Natural Gas: Generator_kBtu":                             "End Use Natural Gas Generator",
    # End Use mazout (kBtu)
    "End Use: Fuel Oil: Heating_kBtu":                                  "End Use Fuel Oil Heating",
    "End Use: Fuel Oil: Heating Heat Pump Backup_kBtu":                 "End Use Fuel Oil Heating Heat Pump Backup",
    "End Use: Fuel Oil: Hot Water_kBtu":                                "End Use Fuel Oil Hot Water",
    "End Use: Fuel Oil: Clothes Dryer_kBtu":                            "End Use Fuel Oil Clothes Dryer",
    "End Use: Fuel Oil: Range/Oven_kBtu":                               "End Use Fuel Oil RangeOven",
    # End Use propane (kBtu)
    "End Use: Propane: Heating_kBtu":                                   "End Use Propane Heating",
    "End Use: Propane: Heating Heat Pump Backup_kBtu":                  "End Use Propane Heating Heat Pump Backup",
    "End Use: Propane: Hot Water_kBtu":                                 "End Use Propane Hot Water",
    "End Use: Propane: Clothes Dryer_kBtu":                             "End Use Propane Clothes Dryer",
    "End Use: Propane: Range/Oven_kBtu":                                "End Use Propane RangeOven",
    # End Use bois (kBtu)
    "End Use: Wood Cord: Heating_kBtu":                                 "End Use Wood Cord Heating",
    "End Use: Wood Cord: Hot Water_kBtu":                               "End Use Wood Cord Hot Water",
    "End Use: Wood Pellets: Heating_kBtu":                              "End Use Wood Pellets Heating",
    "End Use: Wood Pellets: Hot Water_kBtu":                            "End Use Wood Pellets Hot Water",
}

# Noms canoniques provenant de colonnes kBtu -> necessitent conversion
_KBTU_CANONICAL = {canon for raw, canon in _COLUMN_MAPPING.items() if raw.endswith("_kBtu")}


# ---------------------------------------------------------------------------
# Helpers pour construire la liste de KPI
# (miroir de source_kpi_config.py / loaders/source_kpi_config.py)
# ---------------------------------------------------------------------------

def _prism_kpis(column):
    return [
        {"name": "Pente_chauffage", "column": column, "params": {"type_jour": "Tous"}},
        {"name": "Pente_clim",      "column": column, "params": {"type_jour": "Tous"}},
        {"name": "Conso_base",      "column": column, "params": {"type_jour": "Tous"}},
        {"name": "Type_PRISM",      "column": column, "params": {"type_jour": "Tous"}},
    ]


def _profils(column, pas_de_temps="1h"):
    """Profils standard : Hiver/Ete/Annee x Tous/Semaine/FinDeSemaine."""
    entries = []
    for periode in ("Hiver", "Ete", "Annee"):
        for type_jour in ("Tous", "Semaine", "FinDeSemaine"):
            entries.append({
                "name": "Profil",
                "column": column,
                "params": {"pas_de_temps": pas_de_temps, "periode": periode, "type_jour": type_jour},
            })
    return entries


def _all_kpis_for_column(column, with_prism=True, pas_de_temps="1h"):
    kpis = [
        {"name": "Conso_annuelle",       "column": column, "params": {}},
        {"name": "Conso_mensuelle",      "column": column, "params": {}},
        {"name": "Variation_saisonniere","column": column, "params": {}},
        *_profils(column, pas_de_temps=pas_de_temps),
    ]
    if with_prism:
        kpis.extend(_prism_kpis(column))
    return kpis


def _kpis_without_profils(column, with_prism=False):
    kpis = [
        {"name": "Conso_annuelle",       "column": column, "params": {}},
        {"name": "Conso_mensuelle",      "column": column, "params": {}},
        {"name": "Variation_saisonniere","column": column, "params": {}},
    ]
    if with_prism:
        kpis.extend(_prism_kpis(column))
    return kpis


def _end_use_focus_kpis(column, pas_de_temps="1h"):
    return [
        {"name": "Conso_annuelle",        "column": column, "params": {}},
        {"name": "Variation_saisonniere", "column": column, "params": {}},
        {"name": "Conso_mensuelle",       "column": column, "params": {}},
        {"name": "Profil", "column": column, "params": {"pas_de_temps": pas_de_temps, "periode": "Hiver",     "type_jour": "Semaine"}},
        {"name": "Profil", "column": column, "params": {"pas_de_temps": pas_de_temps, "periode": "Ete",       "type_jour": "Semaine"}},
        {"name": "Profil", "column": column, "params": {"pas_de_temps": pas_de_temps, "periode": "Automne",   "type_jour": "Semaine"}},
        {"name": "Profil", "column": column, "params": {"pas_de_temps": pas_de_temps, "periode": "Printemps", "type_jour": "Semaine"}},
        {"name": "Profil", "column": column, "params": {
            "pas_de_temps": pas_de_temps,
            "periode":    "Janvier",
            "type_jour":  "JourPreconfigure",
            "jour_regle": "dernier_mercredi_janvier",
        }},
    ]


_END_USE_COLUMNS = [
    "End Use Electricity Heating",
    "End Use Electricity Heating FansPumps",
    "End Use Electricity Heating Heat Pump Backup",
    "End Use Electricity Heating Heat Pump Backup FansPumps",
    "End Use Electricity Cooling",
    "End Use Electricity Cooling FansPumps",
    "End Use Electricity Hot Water",
    "End Use Electricity Lighting Interior",
    "End Use Electricity Lighting Exterior",
    "End Use Electricity Mech Vent",
    "End Use Electricity Refrigerator",
    "End Use Electricity Freezer",
    "End Use Electricity Dishwasher",
    "End Use Electricity Clothes Washer",
    "End Use Electricity Clothes Dryer",
    "End Use Electricity RangeOven",
    "End Use Electricity Ceiling Fan",
    "End Use Electricity Television",
    "End Use Electricity Plug Loads",
    "End Use Electricity Pool Heater",
    "End Use Electricity Pool Pump",
    "End Use Natural Gas Heating",
    "End Use Natural Gas Heating Heat Pump Backup",
    "End Use Natural Gas Hot Water",
    "End Use Natural Gas Clothes Dryer",
    "End Use Natural Gas RangeOven",
    "End Use Natural Gas Mech Vent Preheating",
    "End Use Natural Gas Pool Heater",
    "End Use Natural Gas Permanent Spa Heater",
    "End Use Natural Gas Grill",
    "End Use Natural Gas Lighting",
    "End Use Natural Gas Fireplace",
    "End Use Natural Gas Generator",
    "End Use Fuel Oil Heating",
    "End Use Fuel Oil Heating Heat Pump Backup",
    "End Use Fuel Oil Hot Water",
    "End Use Fuel Oil Clothes Dryer",
    "End Use Fuel Oil RangeOven",
    "End Use Propane Heating",
    "End Use Propane Heating Heat Pump Backup",
    "End Use Propane Hot Water",
    "End Use Propane Clothes Dryer",
    "End Use Propane RangeOven",
    "End Use Wood Cord Heating",
    "End Use Wood Cord Hot Water",
    "End Use Wood Pellets Heating",
    "End Use Wood Pellets Hot Water",
]

_FUEL_OTHER_COLUMNS = [
    "Fuel Use Natural Gas Total", "Fuel Use Natural Gas Net",
    "Fuel Use Fuel Oil Total",    "Fuel Use Fuel Oil Net",
    "Fuel Use Propane Total",     "Fuel Use Propane Net",
    "Fuel Use Wood Cord Total",   "Fuel Use Wood Cord Net",
    "Fuel Use Wood Pellets Total","Fuel Use Wood Pellets Net",
    "Fuel Use Coal Total",        "Fuel Use Coal Net",
]


def _build_kpi_config(kpi_settings: dict) -> dict:
    """
    Construit la configuration KPI a partir des cles de KPI_SETTING:
      timestep_h        (float)  : pas de temps en heures (defaut 0.25)
      include_prism     (bool)   : PRISM sur Energy Use Total + Electricity Total
      include_profils   (bool)   : Profil sur Energy Use Total + Electricity Total
      include_fuel_totals (bool) : Conso + Mensuelle + Variation sur tous les combustibles
      include_end_use   (bool)   : KPIs End Use
    """
    s = kpi_settings or {}
    timestep_h       = float(s.get("timestep_h",        0.25))
    include_prism    = bool(s.get("include_prism",     True))
    include_profils  = bool(s.get("include_profils",   True))
    include_fuel     = bool(s.get("include_fuel_totals", True))
    include_end_use  = bool(s.get("include_end_use",   True))

    kpis = []

    # Energie totale et nette
    kpis += _all_kpis_for_column(
        "Energy Use Total",
        with_prism=include_prism,
        pas_de_temps="1h" if not include_profils else "1h",
    ) if include_profils else _kpis_without_profils("Energy Use Total", with_prism=include_prism)
    kpis += _all_kpis_for_column("Energy Use Net", with_prism=False, pas_de_temps="1h") \
            if include_profils else _kpis_without_profils("Energy Use Net")

    # Electricite totale et nette
    kpis += _all_kpis_for_column(
        "Fuel Use Electricity Total",
        with_prism=include_prism,
        pas_de_temps="1h",
    ) if include_profils else _kpis_without_profils("Fuel Use Electricity Total", with_prism=include_prism)
    kpis += _all_kpis_for_column("Fuel Use Electricity Net", with_prism=False, pas_de_temps="1h") \
            if include_profils else _kpis_without_profils("Fuel Use Electricity Net")

    # Autres combustibles
    if include_fuel:
        for col in _FUEL_OTHER_COLUMNS:
            kpis += _kpis_without_profils(col)

    # End Use
    if include_end_use:
        for col in _END_USE_COLUMNS:
            kpis += _end_use_focus_kpis(col, pas_de_temps="1h")

    return {
        "datetime_column":    "dateinterval",
        "temperature_column": "temperatureatmospherique",
        "timestep_h":         timestep_h,
        "kpis":               kpis,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Renomme les colonnes et convertit les unites (F→C, kBtu→kWh)."""
    df = df.copy()
    present = {raw: canon for raw, canon in _COLUMN_MAPPING.items() if raw in df.columns}
    df = df[list(present.keys())].rename(columns=present)

    if "dateinterval" in df.columns:
        df["dateinterval"] = pd.to_datetime(df["dateinterval"], errors="coerce")

    if "temperatureatmospherique" in df.columns:
        df["temperatureatmospherique"] = (
            pd.to_numeric(df["temperatureatmospherique"], errors="coerce").sub(32.0).mul(5.0 / 9.0)
        )

    for col in _KBTU_CANONICAL:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce") * _KBTU_TO_KWH

    return df


# ---------------------------------------------------------------------------
# API publique (compatible avec postprocessing.py)
# ---------------------------------------------------------------------------

class Quantite_interet_description:
    """
    Descriptions des KPI produits par Quantite_interet().
    Generees dynamiquement depuis ParametricKPICalculator.get_supported_kpis_metadata().
    Cle = nom du KPI (ex: 'Conso_annuelle'), valeur = dict {Description, Unite, ...}.
    """
    dict_description = ParametricKPICalculator.get_supported_kpis_metadata()


def Quantite_interet(dfTimeseries: pd.DataFrame, kpi_settings: dict = None) -> dict:
    """
    Calcule les quantites d'interet (KPI) a partir des series temporelles
    SimParc brutes (post-jointure multi-header).

    kpi_settings : dict issu de KPI_SETTING dans project.yaml.
                   Cle reconnue : 'timestep_h' (defaut: 1.0).

    Retourne un dict plat {cle_kpi: valeur} pret a etre fusionne dans les
    metadonnees du batiment.  Les cles suivent la convention:
        {nom}__{colonne}__{params}
    ex: "Conso_annuelle__Fuel_Use_Electricity_Total"
        "Pente_chauffage__Fuel_Use_Electricity_Total__type_jour=Tous"
    """
    cfg = _build_kpi_config(kpi_settings)
    df_norm = _normalize(dfTimeseries)
    calculator = ParametricKPICalculator()
    results = calculator.calculate(df_norm, identifiant="", config=cfg)
    results.pop("Identifiant", None)
    return results
