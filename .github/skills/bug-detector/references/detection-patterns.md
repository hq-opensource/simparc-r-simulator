# Patterns de détection de bugs — simparc-r-simulator

## 1. Assignation Pandas silencieuse (Chained Indexing)

**Signature** : `df[masque_booléen]['colonne'] = valeur`

```python
# ❌ BUG — ne modifie pas le DataFrame original (SettingWithCopyWarning)
df[df['col'] == 'val']['autre_col'] = nouvelle_valeur

# ✅ CORRECT
df.loc[df['col'] == 'val', 'autre_col'] = nouvelle_valeur
```

**Où chercher** : toutes les fonctions dans `upgrading.py` qui filtrent puis assignent.

**Exemple connu** : lignes 323-326 et 406-409 — ajustements bi-énergie pour ASHP et MSHP.

---

## 2. Attributs CSV non raccordés au modèle HPXML

**Définition** : colonne présente dans le CSV, stockée dans `non_hpxml_args`, mais jamais lue dans `building.py`, `local.py`, ou transmise à l'OSW.

**Comment vérifier** :
1. Identifier l'attribut dans le CSV (header row)
2. Chercher s'il est dans `args_constraints` → `hpxml_args`
3. Sinon, chercher s'il est lu via `self.non_hpxml_args.get(...)` dans `building.py`
4. Sinon → attribut ignoré 🔵

**Exemples connus** :
- `Vehicule_BornePresence` — jamais lu après stockage
- `Garage Heating Setpoint` — non-HPXML, jamais consommé
- `Basement Heating Setpoint` — non-HPXML, jamais consommé

---

## 3. Écrasement non intentionnel d'un paramètre HPXML

**Signature** : `self.hpxml_args['parametre'] = valeur_calculée` dans `building.py` après que le CSV avait déjà fourni ce paramètre.

**Impact** : la valeur du CSV est ignorée au profit d'une valeur calculée.

**Exemples connus** :
- `hvac_control_cooling_weekday_setpoint` et `hvac_control_cooling_weekend_setpoint` écrasés par `max(chauffage) + 2°F` lors du profil stochastique (lignes 91-92)
- `pool_pump_usage_multiplier` et `pool_heater_usage_multiplier` toujours remis à 1 (lignes 139 et 155)

---

## 4. Conversions d'unités incorrectes ou inconditionnelles

**Signature** : conversion appliquée sans vérification du type d'énergie.

```python
# ❌ BUG — conversion kWh → therms appliquée même pour l'électricité
self.hpxml_args['pool_heater_annual_therm'] = annual_kwh / 29.3

# ✅ CORRECT — conditionner sur le type de combustible
if heater_type != 'electric resistance':
    self.hpxml_args['pool_heater_annual_therm'] = annual_kwh / 29.3
```

**Ambiguïtés d'unités à vérifier** :
- Températures : °C vs °F dans HPXML (HPXML attend toujours des °F)
- R-values : RSI vs R-impérial (1 RSI = 5.678 R)
- Puissances : W vs kW vs BTU/h

---

## 5. Logique de sens inversé

**Signature** : amélioration qui empire la performance.

```python
# ❌ Probable bug — SHGC augmente lors d'une "amélioration" de fenêtre
df['window_shgc'] = df['window_shgc'] * (1 + improvement_rate_shgc)

# ✅ Pour des fenêtres low-e, le SHGC devrait diminuer
df['window_shgc'] = df['window_shgc'] * (1 - improvement_rate_shgc)
```

**Note** : Dans le contexte québécois (gains solaires passifs en hiver), augmenter le SHGC peut être intentionnel. Documenter l'intention.

---

## 6. KeyError potentiel (accès par `[]` au lieu de `.get()`)

**Signature** : `self.non_hpxml_args['cle']` sans valeur par défaut, pour une clé qui pourrait être absente.

```python
# ❌ RISQUE — plante si la colonne est absente du CSV
"Tconsignes_chauffage_H1": self.non_hpxml_args['Tconsignes_chauffage_H1']

# ✅ CORRECT
"Tconsignes_chauffage_H1": self.non_hpxml_args.get('Tconsignes_chauffage_H1')
```

**Où chercher** : `building.py` dans `generate_stochastic_profile()`.

---

## 7. Valeur hardcodée à zéro ou constante ignorant le CSV

**Signature** : `self.hpxml_args['param'] = 0` ou valeur littérale qui devrait venir du CSV.

**Exemple connu** :
- `permanent_spa_pump_annual_kwh = 0` (ligne 188) — la pompe du spa ne consomme jamais d'énergie dans le modèle.

---

## 8. Mise à niveau (upgrade) qui ne propage pas tous les paramètres dépendants

**Signature** : une fonction d'upgrade modifie un paramètre principal mais oublie les paramètres dérivés.

**Exemple** : `decrease_heating_setpoint` modifie uniquement `df['Heating Setpoint']` (le tuple intermédiaire). Si le bâtiment n'utilise pas le profil stochastique, `hvac_control_heating_weekday_setpoint` et `hvac_control_heating_weekend_setpoint` ne sont jamais mis à jour → l'upgrade n'a aucun effet sur la simulation.

---

## 9. Paramètres HPXML non reconnus (silencieusement ignorés par OpenStudio)

**Comment détecter** : chercher dans `hpxml_args` des clés qui ne correspondent à aucun argument de `BuildResidentialHPXML/measure.xml`.

**Risque** : OpenStudio ignore silencieusement les arguments inconnus. Un paramètre mal orthographié (ex: `pool_pump_annual_kwh` vs le bon nom HPXML) ne déclenche aucune erreur mais n'a aucun effet.

**Comment vérifier** : comparer les clés de `hpxml_args` avec `self.cfg["ARGS_CONSTRAINTS"]` (extrait de `measure.xml`).
