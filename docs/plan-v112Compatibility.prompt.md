## 🔴 P1 — CRITIQUE (bloque toutes les simulations)

**1. Corriger le crash `defaults.rb:1181` — nil sur `climate_zone_ieccs[0]`**

**Cause racine identifiée** : Le CSV utilise les anciennes colonnes `air_leakage_value` / `air_leakage_units` (schéma v1.10), mais la mesure actuelle attend `enclosure_air_leakage` (argument TSV). Quand `enclosure_air_leakage` est absent, OpenStudio applique sa valeur par défaut `'Average'` → `leakiness_description = 'average'` s'écrit dans l'HPXML. `BuildResidentialScheduleFile` appelle ensuite `Defaults.apply_infiltration`, qui cherche une zone IECC inexistante pour les fichiers météo canadiens → crash.

**Deux corrections nécessaires** :

- a) **Dans `building-stock-example.csv` (et tous les CSV actifs)** : ajouter une colonne `enclosure_air_leakage` avec la valeur TSV correcte (ex. `"3 ACH50"`) construite depuis `air_leakage_value` + `air_leakage_units` + `air_leakage_house_pressure`. Cette colonne doit être définie dans `hpxml-args-constraints.json`.

- b) **Dans `OpenStudio-HPXML/HPXMLtoOpenStudio/resources/defaults.rb` ligne 1181** : remplacer l'accès direct `climate_zone_ieccs[0].zone` par un guard nil identique aux lignes 3084 et 3404 :
  ```ruby
  # lignes 3084 et 3404 (pattern existant à réutiliser)
  iecc_cz = hpxml_bldg.climate_and_risk_zones.climate_zone_ieccs.empty? ? nil : hpxml_bldg.climate_and_risk_zones.climate_zone_ieccs[0].zone
  ```
  Et dans `get_infiltration_ach50` (ligne ~5970), ajouter un `else` explicite sur `nil` avec un message d'erreur utile ou une zone par défaut canadienne.

---

## 🔴 P2 — CRITIQUE (v1.12, breaking change output)

**2. Vérifier l'impact du renommage de colonne Peak Load : `kBtu/hr` → `Btu/hr`**

- Le rapport de sortie `OpenStudio-HPXML/ReportSimulationOutput` écrit déjà en `Btu/hr` (`peak_load_heating_delivered_btu_hr`).
- L'ancienne version locale `measures/ReportSimulationOutput_old/` utilisait encore `kBtu/hr` (`peak_load_heating_delivered_k_btu_hr`).
- **Vérifier** que ni `postprocessing.py` ni `postprocess/Analyse.py` ni aucun script en aval ne référence le vieux nom de colonne — actuellement aucune référence trouvée, mais à confirmer avec une vraie simulation qui aboutit (bloquée par P1).

---

## 🟡 P3 — MODÉRÉ (migration CSV)

**3. Corriger `hvac_heating_system_fuel` généré à tort quand `hvac_heating_system = 'None'`**

- Dans `tools/migrate_csv.py` : supprimer `hvac_heating_system_fuel` de la ligne de sortie quand la valeur de `hvac_heating_system` est `'None'`.
- Cas de test : `test-migration/test_heating_system_type_1.csv`

---

## 🟡 P4 — MODÉRÉ (robustesse)

**4. Construire la colonne `enclosure_air_leakage` dans `tools/migrate_csv.py`**

- La migration v1.10→v1.12 doit générer `enclosure_air_leakage` (ex. `"3 ACH50"`) à partir de `air_leakage_value` + `air_leakage_units` + `air_leakage_house_pressure`, ou préserver les colonnes qualitatives (`Very Tight`, `Average`, etc.) selon les valeurs présentes.
- Ajouter `enclosure_air_leakage` dans `hpxml-args-constraints.json` avec les choices du TSV.

---

## 🟢 P5 — FAIBLE (tests & gouvernance)

**5. Test de non-régression CLI pour `migrate_csv.py`**  
Tester les cas `input` seul et `input + output`.

**6. Valider en équipe le rechargement SourceTree de `submodule.ignore=dirty`**

**7. Standardiser un smoke test post-`checkout/merge/rebase` (hook + patch QC appliqué)**

---

> **Résumé d'impact** : P1a+P1b débloquent toutes les simulations. P2 est à vérifier mais probablement déjà correct. P3+P4 solidifient la chaîne de migration CSV.
