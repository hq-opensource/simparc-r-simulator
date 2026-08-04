from typing import Dict, Any, Optional
import calendar
import datetime as _dt
import gc

import warnings

import pandas as pd

from src.prism import Prism


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

_SEASON_FILTER_RULES = {
    "Hiver": {
        "min_temp": None,
        "max_temp": 8.0,
        "months": {12, 1, 2, 3, 4},
    },
    "Ete": {
        "min_temp": 15.0,
        "max_temp": None,
        "months": {5, 6, 7, 8, 9, 10, 11},
    },
    "Misaison": {
        "min_temp": 8.0,
        "max_temp": 15.0,
        "months": {4, 5, 6, 9, 10},
    },
    "Tous": {
        "min_temp": None,
        "max_temp": None,
        "months": None,
    },
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
            description="Consommation mensuelle pour un mois donne",
            unit="kWh",
            params={
                "mois": "Mois cible (entier 1-12)",
            },
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
        "EcartType_Quotidien_hiver": KPIMetadata(
            name="EcartType_Quotidien_hiver",
            description=(
                "L'ecart-type journalier moyen de la consommation electrique durant les "
                "journees d'hiver ou la temperature moyenne journaliere est <= 8C "
                "(idealement pour des pas de temps de maximum 1h)"
            ),
            unit="kWh",
            params={},
            required={"datetime", "temperature"},
            sources=None,
        ),
        "EcartType_Quotidien_ete": KPIMetadata(
            name="EcartType_Quotidien_ete",
            description=(
                "L'ecart-type journalier moyen de la consommation electrique durant les "
                "journees d'ete ou la temperature moyenne journaliere est >= 15C "
                "(idealement pour des pas de temps de maximum 1h)"
            ),
            unit="kWh",
            params={},
            required={"datetime", "temperature"},
            sources=None,
        ),
        "EcartType_Quotidien_misaison": KPIMetadata(
            name="EcartType_Quotidien_misaison",
            description=(
                "L'ecart-type journalier moyen de la consommation electrique durant les "
                "journees de misaison ou la temperature moyenne journaliere est entre 8C et 15C "
                "(idealement pour des pas de temps de maximum 1h)"
            ),
            unit="kWh",
            params={},
            required={"datetime", "temperature"},
            sources=None,
        ),
        "FU_Quotidien_hiver": KPIMetadata(
            name="FU_Quotidien_hiver",
            description=(
                "Le facteur d'utilisation en periode hivernale ou la temperature moyenne "
                "journaliere est <= 8C. Le facteur d'utilisation est le rapport entre la "
                "consommation electrique moyenne d'un pas de temps et la consommation "
                "electrique maximale d'un pas de temps. Idealement, le pas de temps est de maximum 1h."
            ),
            unit="-",
            params={},
            required={"datetime", "temperature"},
            sources=None,
        ),
        "FU_Quotidien_ete": KPIMetadata(
            name="FU_Quotidien_ete",
            description=(
                "Le facteur d'utilisation en periode estivale ou la temperature moyenne "
                "journaliere est >= 15C"
            ),
            unit="-",
            params={},
            required={"datetime", "temperature"},
            sources=None,
        ),
        "FU_Quotidien_misaison": KPIMetadata(
            name="FU_Quotidien_misaison",
            description=(
                "Le facteur d'utilisation durant la mi-saison ou la temperature moyenne "
                "journaliere est entre 8C et 15C"
            ),
            unit="-",
            params={},
            required={"datetime", "temperature"},
            sources=None,
        ),
        "RatioJN_Quotidien_hiver": KPIMetadata(
            name="RatioJN_Quotidien_hiver",
            description=(
                "Le ratio entre la consommation electrique moyenne de jour (6h a 22h) et de nuit "
                "durant les journees d'hiver ou la temperature moyenne journaliere est <= 8C"
            ),
            unit="-",
            params={},
            required={"datetime", "temperature"},
            sources=None,
        ),
        "RatioJN_Quotidien_ete": KPIMetadata(
            name="RatioJN_Quotidien_ete",
            description=(
                "Le ratio entre la consommation electrique moyenne de jour (6h a 22h) et de nuit "
                "durant les journees d'ete ou la temperature moyenne journaliere est >= 15C"
            ),
            unit="-",
            params={},
            required={"datetime", "temperature"},
            sources=None,
        ),
        "RatioJN_Quotidien_misaison": KPIMetadata(
            name="RatioJN_Quotidien_misaison",
            description=(
                "Le ratio entre la consommation electrique moyenne de jour (6h a 22h) et de nuit "
                "durant la misaison ou la temperature moyenne journaliere est entre 8C et 15C"
            ),
            unit="-",
            params={},
            required={"datetime", "temperature"},
            sources=None,
        ),
        "EcartType_Quotidien": KPIMetadata(
            name="EcartType_Quotidien",
            description="L'ecart-type journalier moyen de la consommation electrique pour une saison donnee",
            unit="kWh",
            params={
                "saison": "Saison cible : 'Hiver' | 'Ete' | 'Misaison' | 'Tous'",
            },
            required={"datetime", "temperature"},
            sources=None,
        ),
        "FU_Quotidien": KPIMetadata(
            name="FU_Quotidien",
            description="Facteur d'utilisation quotidien moyen pour une saison donnee",
            unit="-",
            params={
                "saison": "Saison cible : 'Hiver' | 'Ete' | 'Misaison' | 'Tous'",
            },
            required={"datetime", "temperature"},
            sources=None,
        ),
        "RatioJN_Quotidien": KPIMetadata(
            name="RatioJN_Quotidien",
            description="Ratio jour/nuit quotidien moyen pour une saison donnee",
            unit="-",
            params={
                "saison": "Saison cible : 'Hiver' | 'Ete' | 'Misaison' | 'Tous'",
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
        "EcartType_Quotidien_hiver":    {"datetime", "temperature"},
        "EcartType_Quotidien_ete":      {"datetime", "temperature"},
        "EcartType_Quotidien_misaison": {"datetime", "temperature"},
        "FU_Quotidien_hiver":           {"datetime", "temperature"},
        "FU_Quotidien_ete":             {"datetime", "temperature"},
        "FU_Quotidien_misaison":        {"datetime", "temperature"},
        "RatioJN_Quotidien_hiver":      {"datetime", "temperature"},
        "RatioJN_Quotidien_ete":        {"datetime", "temperature"},
        "RatioJN_Quotidien_misaison":   {"datetime", "temperature"},
        "EcartType_Quotidien":          {"datetime", "temperature"},
        "FU_Quotidien":                 {"datetime", "temperature"},
        "RatioJN_Quotidien":            {"datetime", "temperature"},
    }

    def __init__(self) -> None:
        # Cache PRISM par colonne energie: un seul ajustement par trace.
        self._prism_cache: Dict[str, Optional[Prism]] = {}
        # Sous-DataFrames saisonniers pre-calcules par calculate() (un groupby pour toutes les saisons).
        self._seasonal_dfs: Dict[str, pd.DataFrame] = {}
        # Cache for filtered dataframes to avoid re-filtering for repeated periode/type_jour
        self._filter_cache: Dict[tuple, pd.DataFrame] = {}

    @classmethod
    def get_supported_kpis_metadata(cls) -> Dict[str, Dict[str, str]]:
        """Retourne les metadonnees des KPI supportes."""
        return {name: meta.to_dict() for name, meta in cls.SUPPORTED_KPIS.items()}

    def calculate(self, df: pd.DataFrame, identifiant: str, config: dict) -> dict:
        """Calcule tous les KPI definis dans *config* et retourne un dict plat de resultats.

        Architecture de calcul (optimisee pour ~1800 KPIs / 84 colonnes):

          Phase 0 - Preparation:
            - Selectionne uniquement les colonnes necessaires (projection minimale).
            - _prepare() ajoute les colonnes auxiliaires: _date, _month, _dayofweek.
            - _build_seasonal_dfs() pre-calcule les sous-DataFrames saisonniers
              (Hiver/Ete/Misaison/Tous) en un seul groupby journalier.

          Phase 1 - Regroupement:
            - Les entrees KPI sont groupees par (kpi_name, params).
            - Ex: les 37 entrees Variation_saisonniere (une par colonne) forment
              un seul groupe appele une seule fois avec 37 colonnes.

          Phase 2 - Dispatch:
            - Chaque groupe appelle _calc_{kpi_name}(df, cols, ...) UNE SEULE FOIS.
            - Chaque _calc_* operes sur TOUTES ses colonnes en vectorise pandas.
            - Resultat: N groupbys au lieu de N_entrees groupbys.

        Args:
            df          : DataFrame charge par un loader (colonnes energie + datetime + temp).
            identifiant : cle du profil (batiment), incluse dans le dict retourne.
            config      : dict source_kpi_config avec cles 'kpis', 'datetime_column',
                          'temperature_column', 'timestep_h'.

        Returns:
            Dict plat {cle_kpi: valeur} ou cle_kpi = '{nom}__{colonne}__{params}'.
            Valeur None si colonne absente ou calcul impossible.
        """
        from collections import defaultdict

        results: Dict[str, Any] = {"Identifiant": identifiant}
        self._prism_cache = {}
        self._filter_cache = {}

        dt_col: Optional[str] = config.get("datetime_column")
        temp_col: Optional[str] = config.get("temperature_column")
        timestep_h: float = float(config.get("timestep_h", 1.0))

        requested_cols = {e.get("column") for e in config.get("kpis", []) if isinstance(e.get("column"), str)}
        base_cols = set(requested_cols)
        if dt_col:
            base_cols.add(dt_col)
        if temp_col:
            base_cols.add(temp_col)

        existing_cols = [c for c in base_cols if c in df.columns]
        df_work = self._prepare(df[existing_cols].copy(), dt_col)
        has_dt = bool(dt_col and dt_col in df_work.columns)
        has_temp = bool(temp_col and temp_col in df_work.columns)

        self._seasonal_dfs = (
            self._build_seasonal_dfs(df_work, temp_col) if has_temp and temp_col else {}
        )

        # --- Phase 1: validate entries and group by (kpi_name, params) ---
        # kpi_groups: (kpi_name, params_tuple) -> [col, col, ...]
        kpi_groups: Dict[tuple, list] = defaultdict(list)

        for entry in config.get("kpis", []):
            kpi_name: str = entry["name"]
            column: str = entry["column"]
            params: dict = entry.get("params", {})
            key = self._make_key(kpi_name, column, params)

            if kpi_name not in self.SUPPORTED_KPIS or column not in df_work.columns:
                results[key] = None
                continue
            req = self.KPI_REQUIRED_STANDARD_COLUMNS.get(kpi_name, set())
            if "datetime" in req and not has_dt:
                results[key] = None
                continue
            if "temperature" in req and not has_temp:
                results[key] = None
                continue

            kpi_groups[(kpi_name, tuple(sorted(params.items())))].append(column)

        # --- Phase 2: call each KPI function once for ALL its columns ---
        for (kpi_name, params_tuple), cols in kpi_groups.items():
            params = dict(params_tuple)
            fn = getattr(self, f"_calc_{kpi_name}", None)
            try:
                if fn is not None:
                    for col, val in fn(df_work, cols, dt_col, temp_col, timestep_h, **params).items():
                        results[self._make_key(kpi_name, col, params)] = val
                else:
                    for col in cols:
                        results[self._make_key(kpi_name, col, params)] = None
            except Exception:
                for col in cols:
                    results[self._make_key(kpi_name, col, params)] = None

        del df_work
        self._prism_cache = {}
        self._seasonal_dfs = {}
        self._filter_cache = {}
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

    # ------------------------------------------------------------------
    # KPI functions: one per KPI type.
    #
    # Architecture:
    #   - Signature uniforme: (df, cols, dt_col, temp_col, timestep_h, **params)
    #     -> Dict[str, Any]  ou les cles sont les noms de colonnes.
    #   - Chaque fonction opere sur TOUTES les colonnes demandees en une seule
    #     operation pandas (groupby, sum, etc.), evitant N appels redondants.
    #   - calculate() regroupe les entrees par (kpi_name, params) et appelle
    #     chaque fonction une seule fois, quelle que soit le nombre de colonnes.
    #   - Les colonnes absentes du DataFrame retournent None sans lever d'exception.
    # ------------------------------------------------------------------

    def _calc_Conso_annuelle(self, df, cols, dt_col, temp_col, timestep_h, **params) -> Dict[str, Any]:
        """Somme annuelle de l'energie (kWh) pour chaque colonne demandee.

        Une seule operation vectorisee df[valid].sum() couvre toutes les colonnes.
        """
        valid = [c for c in cols if c in df.columns]
        sums = df[valid].sum().round(2)
        return {**sums.to_dict(), **{c: None for c in cols if c not in valid}}

    def _calc_Conso_mensuelle(self, df, cols, dt_col, temp_col, timestep_h,
                              mois: Optional[int] = None, **params) -> Dict[str, Any]:
        """Somme mensuelle de l'energie (kWh) pour chaque mois (1-12).
        
        Optimisation de configuration : cette fonction retourne un dictionnaire imbrique
        au lieu de 12 colonnes separees. La config doit avoir **une seule entree par colonne**
        (sans parametre 'mois'), ce qui reduit les KPI de sortie de 12:1.
        
        Le parametre mois est ignore pour retrocompatibilite (les configs anciennes peuvent
        le contenir, mais il n'est pas utilise).

        Algorithme (vectorise pandas):
          1. groupby(_month).sum() -> somme par mois pour toutes les colonnes en 1 operation
          2. Pour chaque colonne, cree {\"1\": sum_jan, \"2\": sum_feb, ..., \"12\": sum_dec}
          3. Les mois absents du DataFrame retournent None (ex: mois incomplet)

        Args:
            df: DataFrame avec colonne _month (1-12)
            cols: colonnes energie a sommer
            dt_col: (non utilise)
            temp_col: (non utilise)
            timestep_h: (non utilise)
            mois: deprecated, ignore. Tous les mois sont toujours calcules.
            **params: parametres additionnels (ignores)

        Returns:
            Dict[str, Any]: {col: {\"1\": sum, \"2\": sum, ..., \"12\": sum}} ou None si col invalide
        """
        valid = [c for c in cols if c in df.columns]
        
        # Calcule la somme pour chaque mois en une seule operation vectorisee
        monthly_sums = df.groupby("_month")[valid].sum().round(2)
        
        result: Dict[str, Any] = {c: None for c in cols if c not in valid}
        for col in valid:
            if col in monthly_sums.columns:
                # Cree un dict avec les mois 1-12 comme cles
                result[col] = {
                    str(m): round(float(monthly_sums.loc[m, col]), 2) if m in monthly_sums.index and pd.notna(monthly_sums.loc[m, col]) else None
                    for m in range(1, 13)
                }
            else:
                result[col] = None
        
        return result

    def _calc_Variation_saisonniere(self, df, cols, dt_col, temp_col, timestep_h, **params) -> Dict[str, Any]:
        """Ratio de la puissance mensuelle moyenne sur la moyenne annuelle (ref = 1.0).

        Algorithme (toutes colonnes en une seule passe):
          1. groupby(_month).mean() -> puissance moyenne par mois (W).
          2. ref = moyenne des 12 mois par colonne.
          3. ratio = puissance_mois / ref, arrondi a 4 decimales.
          4. Retourne {col: {"1": ratio_jan, ..., "12": ratio_dec}}.
        Un mois absent du DataFrame produit None pour ce mois.
        """
        valid = [c for c in cols if c in df.columns]
        monthly_w = df.groupby("_month")[valid].mean() / timestep_h * 1000.0
        ref = monthly_w.mean().replace({0: float("nan")})
        ratios = monthly_w.div(ref).round(4).reindex(range(1, 13))
        result: Dict[str, Any] = {c: None for c in cols if c not in valid}
        for col in valid:
            if pd.isna(ref.get(col)):
                result[col] = None
            else:
                result[col] = {
                    str(m): round(float(ratios.loc[m, col]), 4) if pd.notna(ratios.loc[m, col]) else None
                    for m in range(1, 13)
                }
        return result

    def _calc_Profil(self, df, cols, dt_col, temp_col, timestep_h,
                     pas_de_temps: str = "1h", periode: str = "Annee",
                     type_jour: str = "Tous", jour_regle: Optional[str] = None,
                     **params) -> Dict[str, Any]:
        """Profil intra-journalier moyen en Watts pour chaque colonne.

        Algorithme:
          1. Filtre par periode (saison/mois) et type_jour (Semaine/FinDeSemaine/…).
             Le sous-DataFrame filtre est mis en cache (_filter_cache) pour eviter
             de recalculer le meme filtre pour differentes colonnes.
          2. Un seul groupby par heure (ou slot sub-horaire) couvre toutes les colonnes.
             Pour les donnees sub-horaires, une cle entiere (heure * slots_par_heure +
             slot_dans_heure) remplace strftime (beaucoup plus rapide sur 35k lignes).
          3. Si le pas_de_temps demande differe du pas natif, resampling sur un index
             fictif d'une journee (24-96 valeurs seulement, non sur 35k lignes).
          4. Retourne {col: {"HH:MM:SS": valeur_W, ...}}.

        Args:
            pas_de_temps : resolution souhaitee en sortie ('15min' | '30min' | '1h').
            periode      : filtre temporel ('Annee', 'Hiver', 'Ete', 'Janvier', …).
            type_jour    : filtre jour ('Tous', 'Semaine', 'FinDeSemaine', 'JourPreconfigure').
            jour_regle   : regle textuelle si type_jour='JourPreconfigure'
                           ex: 'dernier_mercredi_janvier'.
        """
        if pas_de_temps == "jour" or not dt_col or dt_col not in df.columns:
            return {col: None for col in cols}
        filter_key = (periode, type_jour, jour_regle)
        if filter_key not in self._filter_cache:
            sub = self._filter_type_jour(self._filter_periode(df, periode), type_jour, jour_regle)
            self._filter_cache[filter_key] = sub
        else:
            sub = self._filter_cache[filter_key]
        if sub.empty:
            return {col: None for col in cols}
        freq_h_map = {"15min": 0.25, "30min": 0.5, "1h": 1.0}
        desired_ts_h = freq_h_map.get(pas_de_temps, timestep_h)
        valid_cols = [c for c in cols if c in sub.columns]
        
        # Step 1: Group by time-of-day (hour:minute:second) and compute mean
        sub = sub.copy()
        sub["_time"] = sub[dt_col].dt.strftime("%H:%M:%S")
        grouped = sub.groupby("_time")[valid_cols].mean()
        time_labels = grouped.index.tolist()
        
        # Step 2: Convert to Watts (divide by timestep_h in hours, multiply by 1000 to get W)
        profile_w = grouped / timestep_h * 1000.0
        
        # Step 3: Resample to desired output timestep if different
        if desired_ts_h != timestep_h:
            # Create an intraday index with source timestep, then resample
            native_idx = pd.date_range("2000-01-01", periods=len(profile_w), freq=f"{int(timestep_h * 60)}min")
            out_freq = {0.25: "15min", 0.5: "30min", 1.0: "h"}.get(desired_ts_h, "h")
            profile_w = profile_w.set_index(native_idx).resample(out_freq).mean()
            time_labels = profile_w.index.strftime("%H:%M:%S").tolist()
        
        result: Dict[str, Any] = {c: None for c in cols if c not in valid_cols}
        for col in valid_cols:
            result[col] = {t: round(float(v), 2) for t, v in zip(time_labels, profile_w[col]) if pd.notna(v)}
        return result

    def _calc_EcartType_Quotidien(self, df, cols, dt_col, temp_col, timestep_h,
                                   saison: str = "Tous", **params) -> Dict[str, Any]:
        """Ecart-type journalier moyen de la consommation pour une saison donnee.

        Algorithme: filtre saisonnier -> groupby(_date).std() -> moyenne des ecarts-types
        journaliers sur toutes les colonnes en une seule operation.

        Args:
            saison: 'Hiver' (T<=8C) | 'Ete' (T>=15C) | 'Misaison' (8C<T<15C) | 'Tous'.
        """
        sub = self._seasonal_filter(df, temp_col, saison)
        if sub.empty:
            return {col: None for col in cols}
        valid = [c for c in cols if c in sub.columns]
        means = sub.groupby("_date")[valid].std().mean().round(4)
        return {**means.to_dict(), **{c: None for c in cols if c not in valid}}

    def _calc_FU_Quotidien(self, df, cols, dt_col, temp_col, timestep_h,
                           saison: str = "Tous", **params) -> Dict[str, Any]:
        """Facteur d'utilisation quotidien moyen (mean/max par jour) pour une saison.

        FU = moyenne_journaliere / maximum_journalier, moyenne sur tous les jours.
        Toutes les colonnes sont traitees en une seule passe groupby.

        Args:
            saison: 'Hiver' | 'Ete' | 'Misaison' | 'Tous'.
        """
        sub = self._seasonal_filter(df, temp_col, saison)
        if sub.empty:
            return {col: None for col in cols}
        valid = [c for c in cols if c in sub.columns]
        grp = sub.groupby("_date")[valid]
        means = (grp.mean() / grp.max().replace({0: float("nan")})).mean().round(4)
        return {**means.to_dict(), **{c: None for c in cols if c not in valid}}

    def _calc_RatioJN_Quotidien(self, df, cols, dt_col, temp_col, timestep_h,
                                saison: str = "Tous", **params) -> Dict[str, Any]:
        """Ratio consommation jour / nuit quotidien moyen pour une saison.

        Jour  : 6h-21h inclus. Nuit : 22h-5h inclus.
        Algorithme: filtre saisonnier -> split jour/nuit -> groupby(_date).mean()
        sur toutes les colonnes -> ratio -> moyenne sur les jours communs.

        Args:
            saison: 'Hiver' | 'Ete' | 'Misaison' | 'Tous'.
        """
        if not dt_col or dt_col not in df.columns:
            return {col: None for col in cols}
        sub = self._seasonal_filter(df, temp_col, saison)
        if sub.empty:
            return {col: None for col in cols}
        valid = [c for c in cols if c in sub.columns]
        day_mask = (sub[dt_col].dt.hour >= 6) & (sub[dt_col].dt.hour <= 21)
        day_grp = sub[day_mask].groupby("_date")[valid].mean()
        night_grp = sub[~day_mask].groupby("_date")[valid].mean()
        idx = day_grp.index.intersection(night_grp.index)
        if idx.empty:
            return {col: None for col in cols}
        means = (day_grp.loc[idx] / night_grp.loc[idx].replace({0: float("nan")})).mean().round(4)
        return {**means.to_dict(), **{c: None for c in cols if c not in valid}}

    # Seasonal variants — thin wrappers that fix the saison parameter so that
    # calculate() can resolve them by KPI name without extra params dispatch.
    def _calc_EcartType_Quotidien_hiver(self, df, cols, *a, **kw):
        return self._calc_EcartType_Quotidien(df, cols, *a, saison="Hiver", **kw)
    def _calc_EcartType_Quotidien_ete(self, df, cols, *a, **kw):
        return self._calc_EcartType_Quotidien(df, cols, *a, saison="Ete", **kw)
    def _calc_EcartType_Quotidien_misaison(self, df, cols, *a, **kw):
        return self._calc_EcartType_Quotidien(df, cols, *a, saison="Misaison", **kw)
    def _calc_FU_Quotidien_hiver(self, df, cols, *a, **kw):
        return self._calc_FU_Quotidien(df, cols, *a, saison="Hiver", **kw)
    def _calc_FU_Quotidien_ete(self, df, cols, *a, **kw):
        return self._calc_FU_Quotidien(df, cols, *a, saison="Ete", **kw)
    def _calc_FU_Quotidien_misaison(self, df, cols, *a, **kw):
        return self._calc_FU_Quotidien(df, cols, *a, saison="Misaison", **kw)
    def _calc_RatioJN_Quotidien_hiver(self, df, cols, *a, **kw):
        return self._calc_RatioJN_Quotidien(df, cols, *a, saison="Hiver", **kw)
    def _calc_RatioJN_Quotidien_ete(self, df, cols, *a, **kw):
        return self._calc_RatioJN_Quotidien(df, cols, *a, saison="Ete", **kw)
    def _calc_RatioJN_Quotidien_misaison(self, df, cols, *a, **kw):
        return self._calc_RatioJN_Quotidien(df, cols, *a, saison="Misaison", **kw)

    # PRISM — fitted per column, results collected into a dict.
    def _calc_Pente_chauffage(self, df, cols, dt_col, temp_col, timestep_h, **params) -> Dict[str, Any]:
        return {col: self._get_prism_param_by_prefix(self._run_prism(df, col, temp_col), "kch") for col in cols}
    def _calc_Pente_clim(self, df, cols, dt_col, temp_col, timestep_h, **params) -> Dict[str, Any]:
        return {col: self._get_prism_param_by_prefix(self._run_prism(df, col, temp_col), "kcl") for col in cols}
    def _calc_Conso_base(self, df, cols, dt_col, temp_col, timestep_h, **params) -> Dict[str, Any]:
        return {col: (self._run_prism(df, col, temp_col) or type("", (), {"param": {}})()).param.get("Base [kW]") for col in cols}
    def _calc_Type_PRISM(self, df, cols, dt_col, temp_col, timestep_h, **params) -> Dict[str, Any]:
        return {col: getattr(self._run_prism(df, col, temp_col), "model", None) for col in cols}

    def _run_prism(self, df: pd.DataFrame, col: str, temp_col: str) -> Optional[Prism]:
        """Ajuste le modele PRISM sur les donnees journalieres d'une colonne.

        Le resultat est mis en cache (_prism_cache) par colonne: un seul ajustement
        par colonne et par appel a calculate(), reutilise par Pente_chauffage,
        Pente_clim, Conso_base et Type_PRISM.

        Args:
            col     : nom de la colonne energie (kWh/pas).
            temp_col: nom de la colonne temperature exterieure (degC).

        Returns:
            Instance Prism ajustee, ou None si donnees insuffisantes (< 10 jours).
        """
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
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=RuntimeWarning)
            prism.calcul()
        self._prism_cache[col] = prism
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

    def _build_seasonal_dfs(self, df: pd.DataFrame, temp_col: str) -> Dict[str, pd.DataFrame]:
        """Pre-calcule les sous-DataFrames saisonniers en un seul groupby journalier.

        Les saisons sont definies par temperature moyenne journaliere (PRISM-like):
          - Hiver   : T <= 8 C  (mois 12,1,2,3,4)
          - Ete     : T >= 15 C (mois 5..11)
          - Misaison: 8 C < T < 15 C (mois 4,5,6,9,10)

        Appele une seule fois par calculate() avant la boucle KPI. Les sous-DataFrames
        sont stockes dans self._seasonal_dfs et accedes via _seasonal_filter().
        """
        if df.empty:
            return {s: df for s in _SEASON_FILTER_RULES}
        daily = df.groupby("_date", as_index=False).agg(temp=(temp_col, "mean"))
        daily["_month"] = pd.to_datetime(daily["_date"]).dt.month
        result: Dict[str, pd.DataFrame] = {"Tous": df}
        for season_name, rule in _SEASON_FILTER_RULES.items():
            if season_name == "Tous":
                continue
            mask = pd.Series(True, index=daily.index)
            if rule["min_temp"] is not None:
                mask &= (daily["temp"] > rule["min_temp"] if season_name == "Misaison"
                         else daily["temp"] >= rule["min_temp"])
            if rule["max_temp"] is not None:
                mask &= (daily["temp"] < rule["max_temp"] if season_name == "Misaison"
                         else daily["temp"] <= rule["max_temp"])
            if rule["months"] is not None:
                mask &= daily["_month"].isin(rule["months"])
            result[season_name] = df[df["_date"].isin(set(daily[mask]["_date"]))]
        return result

    def _seasonal_filter(self, df: pd.DataFrame, temp_col: str, saison: str = "Tous") -> pd.DataFrame:
        """Retourne le sous-DataFrame saissonnier pre-calcule pour la saison demandee.

        Les sous-DataFrames sont construits une seule fois par calculate() via
        _build_seasonal_dfs(). Cette methode est un simple acces en cache O(1).

        Args:
            saison: 'Hiver' | 'Ete' | 'Misaison' | 'Tous'
        """
        season_name = str(saison or "Tous").strip().capitalize()
        if season_name not in _SEASON_FILTER_RULES:
            season_name = "Tous"
        return self._seasonal_dfs.get(season_name, df)
