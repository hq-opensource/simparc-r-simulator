from typing import Dict, Any, Optional
import calendar
import datetime as _dt
import gc

import pandas as pd

from postprocess.prism import Prism


class KPIMetadata:
    """
    Metadonnees d'un KPI.

    Attributs
    ---------
    name        : identifiant interne (correspond a la cle dans SUPPORTED_KPIS)
    description : description courte
    unit        : unite du resultat
    params      : dict {nom_param: description_param} -- parametres acceptes par le KPI
    required    : ensemble des colonnes logiques requises dans le DataFrame
                  ("datetime" = colonne date/heure ; "temperature" = temperature exterieure)
    sources     : liste des sources de donnees compatibles (None = toutes)
    """

    def __init__(
        self,
        name: str,
        description: str,
        unit: str,
        params: Optional[Dict[str, str]] = None,
        required: Optional[set[str]] = None,
        sources: Optional[list[str]] = None,
    ):
        self.name = name
        self.description = description
        self.unit = unit
        self.params: Dict[str, str] = params or {}
        self.required: set[str] = required or set()
        self.sources: Optional[list[str]] = sources

    def to_dict(self) -> Dict[str, Any]:
        return {
            "Nom": self.name,
            "Description": self.description,
            "Unite": self.unit,
            "Parametres": self.params,
            "Colonnes requises": sorted(self.required),
            "Sources": self.sources,
        }


# ---------------------------------------------------------------------------
# Dictionnaires de correspondance pour le systeme parametrique
# ---------------------------------------------------------------------------

_MONTH_NAMES_FR = {
    "Janvier": 1,
    "Fevrier": 2,
    "Mars": 3,
    "Avril": 4,
    "Mai": 5,
    "Juin": 6,
    "Juillet": 7,
    "Aout": 8,
    "Septembre": 9,
    "Octobre": 10,
    "Novembre": 11,
    "Decembre": 12,
}

_SEASON_MONTHS = {
    "Hiver": [12, 1, 2],
    "Printemps": [3, 4, 5],
    "Ete": [6, 7, 8],
    "Automne": [9, 10, 11],
}

_WEEKDAY_FR = {
    "lundi": 0,
    "mardi": 1,
    "mercredi": 2,
    "jeudi": 3,
    "vendredi": 4,
    "samedi": 5,
    "dimanche": 6,
}

_MONTH_FR_LOWER = {
    "janvier": 1,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
}


class ParametricKPICalculator:
    """
    Calculateur KPI entierement parametrique.

    Chaque entree de la liste ``kpis`` dans la config produit exactement un
    resultat dans le dict retourne, avec une cle auto-generee ::

        {nom}__{colonne}__{params}
    """

    SUPPORTED_KPIS: Dict[str, KPIMetadata] = {
        # ------------------------------------------------------------------
        # KPI sans temperature requise (toutes sources)
        # ------------------------------------------------------------------
        "Conso_annuelle": KPIMetadata(
            name="Conso_annuelle",
            description="Consommation annuelle totale de la colonne selectionnee",
            unit="kWh",
            params={},
            required=set(),
            sources=None,
        ),
        "Conso_mensuelle": KPIMetadata(
            name="Conso_mensuelle",
            description="Puissance moyenne pour un mois donne",
            unit="W",
            params={},
            required={"datetime"},
            sources=None,
        ),
        "Variation_saisonniere": KPIMetadata(
            name="Variation_saisonniere",
            description="Ratio de la puissance mensuelle sur la moyenne des 12 mois (reference=1.0)",
            unit="-",
            params={},
            required={"datetime"},
            sources=None,
        ),
        "Profil": KPIMetadata(
            name="Profil",
            description="Profil moyen intra-journalier par pas de temps",
            unit="W",
            params={
                "pas_de_temps": "Resolution temporelle : '15min' | '30min' | '1h'",
                "periode": (
                    "Filtre temporel : 'Annee' | 'Tous' | 'Hiver' | 'Printemps' | 'Ete' | 'Automne' "
                    "| 'Janvier' | 'Fevrier' | 'Mars' | 'Avril' | 'Mai' | 'Juin' "
                    "| 'Juillet' | 'Aout' | 'Septembre' | 'Octobre' | 'Novembre' | 'Decembre'"
                ),
                "type_jour": (
                    "Type de jour : 'Tous' | 'Semaine' | 'FinDeSemaine' | 'JourPreconfigure'"
                ),
                "jour_regle": (
                    "Regle textuelle si type_jour='JourPreconfigure' "
                    "ex: 'dernier_mercredi_janvier', 'premier_lundi_mars'"
                ),
            },
            required={"datetime"},
            sources=None,
        ),
        # ------------------------------------------------------------------
        # KPI PRISM (temperature obligatoire)
        # ------------------------------------------------------------------
        "Pente_chauffage": KPIMetadata(
            name="Pente_chauffage",
            description="Pente de chauffage issue du modele PRISM (kch)",
            unit="W/C",
            params={
                "type_jour": "Type de jour utilise pour l'agregation journaliere : 'Tous' | 'Semaine' | 'FinDeSemaine'",
            },
            required={"datetime", "temperature"},
            sources=None,
        ),
        "Pente_clim": KPIMetadata(
            name="Pente_clim",
            description="Pente de climatisation issue du modele PRISM (kcl)",
            unit="W/C",
            params={
                "type_jour": "Type de jour utilise pour l'agregation journaliere : 'Tous' | 'Semaine' | 'FinDeSemaine'",
            },
            required={"datetime", "temperature"},
            sources=None,
        ),
        "Conso_base": KPIMetadata(
            name="Conso_base",
            description="Consommation de base issue du modele PRISM (intercept)",
            unit="kW",
            params={
                "type_jour": "Type de jour utilise pour l'agregation journaliere : 'Tous' | 'Semaine' | 'FinDeSemaine'",
            },
            required={"datetime", "temperature"},
            sources=None,
        ),
        "Type_PRISM": KPIMetadata(
            name="Type_PRISM",
            description="Type de modele PRISM retenu par l'algorithme d'ajustement",
            unit="-",
            params={
                "type_jour": "Type de jour utilise pour l'agregation journaliere : 'Tous' | 'Semaine' | 'FinDeSemaine'",
            },
            required={"datetime", "temperature"},
            sources=None,
        ),
    }

    # KPI_REQUIRED_STANDARD_COLUMNS derive automatiquement de SUPPORTED_KPIS.required
    # pour etre la source de verite unique.
    @classmethod
    def _get_required(cls, kpi_name: str) -> set[str]:
        meta = cls.SUPPORTED_KPIS.get(kpi_name)
        return meta.required if meta else set()

    KPI_REQUIRED_STANDARD_COLUMNS: Dict[str, set[str]] = {
        "Conso_annuelle":        set(),
        "Conso_mensuelle":       {"datetime"},
        "Variation_saisonniere": {"datetime"},
        "Profil":                {"datetime"},
        "Pente_chauffage":       {"datetime", "temperature"},
        "Pente_clim":            {"datetime", "temperature"},
        "Conso_base":            {"datetime", "temperature"},
        "Type_PRISM":            {"datetime", "temperature"},
    }

    def __init__(self) -> None:
        # Cache PRISM par colonne energie: un seul ajustement par trace.
        self._prism_cache: Dict[str, Optional[Prism]] = {}

    @classmethod
    def get_supported_kpis_metadata(cls) -> Dict[str, Dict[str, str]]:
        """Retourne les metadonnees des KPI supportes."""
        return {name: meta.to_dict() for name, meta in cls.SUPPORTED_KPIS.items()}

    def calculate(self, df: pd.DataFrame, identifiant: str, config: dict) -> dict:
        """Calcule tous les KPI definis dans *config* et retourne un dict de resultats."""
        results: Dict[str, Any] = {"Identifiant": identifiant}
        self._prism_cache = {}

        dt_col: Optional[str] = config.get("datetime_column")
        temp_col: Optional[str] = config.get("temperature_column")
        timestep_h: float = float(config.get("timestep_h", 1.0))

        requested_cols = {entry.get("column") for entry in config.get("kpis", [])}
        requested_cols = {c for c in requested_cols if isinstance(c, str)}

        base_cols = set(requested_cols)
        if dt_col:
            base_cols.add(dt_col)
        if temp_col:
            base_cols.add(temp_col)

        existing_cols = [c for c in base_cols if c in df.columns]
        # Copie reduite au strict necessaire pour limiter l'empreinte memoire.
        df_work = self._prepare(df[existing_cols].copy(), dt_col)
        has_dt = bool(dt_col and dt_col in df_work.columns)
        has_temp = bool(temp_col and temp_col in df_work.columns)

        for entry in config.get("kpis", []):
            kpi_name: str = entry["name"]
            column: str = entry["column"]
            params: dict = entry.get("params", {})
            key = self._make_key(kpi_name, column, params)

            if kpi_name not in self.SUPPORTED_KPIS:
                results[key] = None
                continue
            if column not in df_work.columns:
                results[key] = None
                continue
            if "datetime" in self.KPI_REQUIRED_STANDARD_COLUMNS.get(kpi_name, set()) and not has_dt:
                results[key] = None
                continue
            if "temperature" in self.KPI_REQUIRED_STANDARD_COLUMNS.get(kpi_name, set()) and not has_temp:
                results[key] = None
                continue

            fn = getattr(self, f"_calc_{kpi_name}", None)
            if fn is None:
                results[key] = None
                continue

            try:
                results[key] = fn(df_work, column, dt_col, temp_col, timestep_h, **params)
            except Exception:
                results[key] = None

        del df_work
        self._prism_cache = {}
        gc.collect()

        return results

    def _prepare(self, df: pd.DataFrame, dt_col: Optional[str]) -> pd.DataFrame:
        df = df.copy()
        if dt_col and dt_col in df.columns:
            if not pd.api.types.is_datetime64_any_dtype(df[dt_col]):
                df[dt_col] = pd.to_datetime(df[dt_col], errors="coerce")
            df["_date"] = df[dt_col].dt.date
            df["_month"] = df[dt_col].dt.month
            df["_dayofweek"] = df[dt_col].dt.dayofweek
        return df

    @staticmethod
    def _make_key(name: str, column: str, params: dict) -> str:
        col_safe = column.replace(" ", "_")
        if not params:
            return f"{name}__{col_safe}"
        params_str = "__".join(f"{k}={v}" for k, v in sorted(params.items()))
        return f"{name}__{col_safe}__{params_str}"

    def _filter_periode(self, df: pd.DataFrame, periode: str) -> pd.DataFrame:
        if not periode or periode in ("Annee", "Tous"):
            return df
        if periode in _SEASON_MONTHS:
            return df[df["_month"].isin(_SEASON_MONTHS[periode])]
        if periode in _MONTH_NAMES_FR:
            return df[df["_month"] == _MONTH_NAMES_FR[periode]]
        return df

    def _filter_type_jour(self, df: pd.DataFrame, type_jour: str, jour_regle: Optional[str] = None) -> pd.DataFrame:
        if not type_jour or type_jour == "Tous":
            return df
        if type_jour == "Semaine":
            return df[df["_dayofweek"] < 5]
        if type_jour == "FinDeSemaine":
            return df[df["_dayofweek"] >= 5]
        if type_jour == "JourPreconfigure" and jour_regle:
            dates = self._resolve_regle(df, jour_regle)
            return df[df["_date"].isin(dates)]
        return df

    def _resolve_regle(self, df: pd.DataFrame, regle: str) -> list:
        parts = regle.lower().split("_")
        if len(parts) < 3:
            return []

        ordinal, weekday_name, month_name = parts[0], parts[1], "_".join(parts[2:])
        if weekday_name not in _WEEKDAY_FR or month_name not in _MONTH_FR_LOWER:
            return []

        target_wd = _WEEKDAY_FR[weekday_name]
        target_mo = _MONTH_FR_LOWER[month_name]

        unique_years: set = set()
        if "_date" in df.columns:
            unique_years = {d.year for d in df["_date"] if hasattr(d, "year")}

        result: list = []
        for year in unique_years:
            cal = calendar.monthcalendar(year, target_mo)
            occurrences = [_dt.date(year, target_mo, week[target_wd]) for week in cal if week[target_wd] != 0]
            if not occurrences:
                continue
            result.append(occurrences[0] if ordinal == "premier" else occurrences[-1])
        return result

    def _calc_Conso_annuelle(self, df, col, dt_col, temp_col, timestep_h, **params) -> float:
        return round(float(df[col].sum()), 2)

    def _calc_Conso_mensuelle(self, df, col, dt_col, temp_col, timestep_h, mois: Optional[int] = None, **params) -> Optional[dict]:
        result: Dict[str, Optional[float]] = {}
        for m in range(1, 13):
            sub = df[df["_month"] == m][col]
            if sub.empty or timestep_h <= 0:
                result[str(m)] = None
                continue
            result[str(m)] = round(float(sub.mean()) / timestep_h * 1000.0, 2)

        if all(v is None for v in result.values()):
            return None
        return result

    def _calc_Variation_saisonniere(self, df, col, dt_col, temp_col, timestep_h, mois: Optional[int] = None, **params) -> Optional[dict]:
        monthly_w: Dict[int, Optional[float]] = {}
        for m in range(1, 13):
            sub = df[df["_month"] == m][col]
            if sub.empty:
                monthly_w[m] = None
                continue
            # Moyenne mensuelle de puissance (W) basee sur la moyenne des pas.
            # Ratio final sans unite: la conversion en W s'annule, mais on garde
            # la meme convention que les autres KPI de puissance.
            monthly_w[m] = float(sub.mean()) / timestep_h * 1000.0 if timestep_h > 0 else None

        valid = [v for v in monthly_w.values() if v is not None]
        if not valid:
            return None
        ref = sum(valid) / len(valid)
        if ref == 0:
            return None

        result: Dict[str, Optional[float]] = {}
        for m in range(1, 13):
            value = monthly_w.get(m)
            result[str(m)] = round(value / ref, 4) if value is not None else None
        return result

    def _calc_Profil(
        self,
        df,
        col,
        dt_col,
        temp_col,
        timestep_h,
        pas_de_temps: str = "1h",
        periode: str = "Annee",
        type_jour: str = "Tous",
        jour_regle: Optional[str] = None,
        **params,
    ) -> Optional[dict]:
        if pas_de_temps == "jour" or not dt_col or dt_col not in df.columns:
            return None

        sub = self._filter_periode(df, periode)
        sub = self._filter_type_jour(sub, type_jour, jour_regle)
        if sub.empty:
            return None

        freq_map = {"15min": "15min", "30min": "30min", "1h": "h"}
        freq_h_map = {"15min": 0.25, "30min": 0.5, "1h": 1.0}
        freq = freq_map.get(pas_de_temps, "h")
        ts_h = freq_h_map.get(pas_de_temps, timestep_h)

        ts = sub.set_index(dt_col)[[col]].resample(freq)[col].mean()
        ts_w = ts / ts_h * 1000.0

        time_labels = ts_w.index.strftime("%H:%M:%S")
        profile = ts_w.groupby(time_labels).mean()
        return {t: round(float(v), 2) for t, v in profile.items() if pd.notna(v)}

    def _run_prism(self, df: pd.DataFrame, col: str, temp_col: str) -> Optional[Prism]:
        if col in self._prism_cache:
            return self._prism_cache[col]

        if df.empty or "_date" not in df.columns:
            self._prism_cache[col] = None
            return None

        daily = df.groupby("_date", as_index=False).agg(e=(col, "sum"), t=(temp_col, "mean"))
        if len(daily) < 10:
            self._prism_cache[col] = None
            return None

        prism = Prism(QuotikWh=daily["e"].tolist(), QuotiTemp=daily["t"].tolist())
        import warnings
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=RuntimeWarning)
            prism.calcul()
        self._prism_cache[col] = prism

        del daily
        gc.collect()

        return prism

    @staticmethod
    def _get_prism_param_by_prefix(prism: Prism, prefix: str) -> Optional[float]:
        if prism is None or not getattr(prism, "param", None):
            return None
        pfx = prefix.lower()
        for key, value in prism.param.items():
            if isinstance(key, str) and key.lower().startswith(pfx):
                return value
        return None

    def _calc_Pente_chauffage(self, df, col, dt_col, temp_col, timestep_h, **params) -> Optional[float]:
        prism = self._run_prism(df, col, temp_col)
        return self._get_prism_param_by_prefix(prism, "kch")

    def _calc_Pente_clim(self, df, col, dt_col, temp_col, timestep_h, **params) -> Optional[float]:
        prism = self._run_prism(df, col, temp_col)
        return self._get_prism_param_by_prefix(prism, "kcl")

    def _calc_Conso_base(self, df, col, dt_col, temp_col, timestep_h, **params) -> Optional[float]:
        prism = self._run_prism(df, col, temp_col)
        if prism is None or not prism.param:
            return None
        return prism.param.get("Base [kW]")

    def _calc_Type_PRISM(self, df, col, dt_col, temp_col, timestep_h, **params) -> Optional[str]:
        prism = self._run_prism(df, col, temp_col)
        return getattr(prism, "model", None) if prism else None
