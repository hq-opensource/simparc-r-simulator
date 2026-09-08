## 🔴 P1 — CRITIQUE (bloque toutes les simulations)

**1. Corriger le crash `defaults.rb:1181` — nil sur `climate_zone_ieccs[0]`**

**Cause racine identifiée** : Le CSV utilise les anciennes colonnes `air_leakage_value` / `air_leakage_units` (schéma v1.10), mais la mesure actuelle attend `enclosure_air_leakage` (argument TSV). Quand `enclosure_air_leakage` est absent, OpenStudio applique sa valeur par défaut `'Average'` → `leakiness_description = 'average'` s'écrit dans l'HPXML. `BuildResidentialScheduleFile` appelle ensuite `Defaults.apply_infiltration`, qui cherche une zone IECC inexistante pour les fichiers météo canadiens → crash.

**Deux corrections nécessaires** :

- **P1a) Construire `enclosure_air_leakage` dans le pipeline de preprocessing**
  - La logique de construction est maintenant disponible dans `tools/migrate_csv.py` → fonction `build_enclosure_air_leakage_value()` (✅ Sep 3, 2026)
  - **À implémenter** : Ajouter la même logique à `preprocessing.py` pour construire `enclosure_air_leakage` à partir de `air_leakage_value`, `air_leakage_units`, `air_leakage_house_pressure`
  - Cette colonne doit être définie dans `hpxml-args-constraints.json` avec les choices du TSV `enclosure_air_leakage.tsv`

- **P1b) Ajouter nil guard sur `climate_zone_ieccs[0]` dans `defaults.rb:1181`** : remplacer l'accès direct `climate_zone_ieccs[0].zone` par un guard nil identique aux lignes 3084 et 3404 :
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

## ✅ P4 — RÉSOLU (Sep 3, 2026)

**4. Construire la colonne `enclosure_air_leakage` dans `tools/migrate_csv.py`** ✅ **FAIT**

- ✅ Migration v1.10→v1.12 génère maintenant `enclosure_air_leakage` (ex. `"3 ACH50"`) à partir de `air_leakage_value` + `air_leakage_units` + `air_leakage_house_pressure`
- ✅ Fonction `build_enclosure_air_leakage_value()` supporte ACH, CFM, et natural ACH
- ✅ Validation des colonnes requises avec messages d'erreur clairs
- ✅ Format TSV conforme aux choix de `enclosure_air_leakage.tsv`
- **Suivant** : réutiliser cette logique pour P1a dans `preprocessing.py`

---

## 🟢 P5 — FAIBLE (tests & gouvernance)

**5. Test de non-régression CLI pour `migrate_csv.py`**  
Tester les cas `input` seul et `input + output`.

**6. Valider en équipe le rechargement SourceTree de `submodule.ignore=dirty`**

**7. Standardiser un smoke test post-`checkout/merge/rebase` (hook + patch QC appliqué)**

---

> **Résumé d'impact** : 
> - ✅ **P4 résolu** (Sep 3, 2026) — `tools/migrate_csv.py` construit maintenant `enclosure_air_leakage` correctement
> - 🔴 **P1a reste critique** — Implémenter la même logique dans `preprocessing.py` pour le pipeline de simulation
> - 🔴 **P1b reste critique** — Ajouter nil guard dans `defaults.rb:1181`
> - P1a+P1b débloquent toutes les simulations v1.12
> - P2 à vérifier après P1 fixé (probablement déjà correct)
> - P3 solidifie migration CSV (spurious hvac_heating_system_fuel)
