---
name: bug-detector
description: "Analyser le code Python pour détecter des bugs potentiels : assignations Pandas silencieuses (chained indexing), logique erronée, paramètres HPXML mal raccordés, attributs CSV ignorés, conversions d'unités incorrectes. Use when: auditing code, finding bugs, reviewing CSV attribute pipeline, checking HPXML mapping, debugging silent failures, chained assignment, SettingWithCopyWarning."
argument-hint: "fichier ou module à analyser (ex: upgrading.py, building.py)"
---

# Bug Detector — simparc-r-simulator

## Ce que fait cette skill

Audite le code Python du simulateur de parc de bâtiments pour repérer des **bugs potentiels** affectant le modèle HPXML/OpenStudio/EnergyPlus. Elle cible en priorité les erreurs silencieuses qui ne font pas planter la simulation mais produisent des résultats incorrects.

## Quand l'utiliser

- "Repère les bugs dans [fichier]"
- "Audite le pipeline CSV → HPXML"
- "Y a-t-il des attributs du CSV qui ne sont pas correctement raccordés au modèle ?"
- "Cherche des assignations Pandas silencieuses"
- "Vérifie les conversions d'unités"

## Procédure d'audit

### Étape 1 — Lire les fichiers ciblés
Lire les fichiers Python pertinents, en commençant par :
- `preprocessing.py` — typage et séparation hpxml_args / non_hpxml_args
- `building.py` — génération de profils stochastiques et création de l'OSW
- `upgrading.py` — fonctions d'amélioration appliquées aux DataFrames
- `local.py` — pipeline principal (run_building, run_batch)

### Étape 2 — Appliquer les patterns de détection

Consulter [les patterns de détection](./references/detection-patterns.md) pour chaque catégorie de bug.

### Étape 3 — Rapporter

Pour chaque bug trouvé, produire un rapport structuré :
```
🔴/🟡/🔵 [Gravité] Titre court
Fichier : nom_fichier.py, ligne(s) X-Y
Attribut(s) concerné(s) : colonne CSV ou paramètre HPXML
Problème : description précise de ce qui est incorrect
Conséquence : impact sur la simulation (résultat erroné, valeur ignorée, crash)
Correction suggérée : extrait de code corrigé
```

Niveaux de gravité :
- 🔴 **Bug confirmé** — la valeur CSV n'est pas appliquée au modèle comme prévu
- 🟡 **Risque** — comportement ambigu ou dépendant d'hypothèses non documentées
- 🔵 **Attribut ignoré** — colonne CSV présente mais jamais consommée dans le pipeline

### Étape 4 — Résumé final

Lister en tableau :
| # | Gravité | Fichier | Attribut(s) | Impact |
|---|---------|---------|-------------|--------|
| 1 | 🔴 | upgrading.py | Source_Energie_Chauf | Bi-énergie non appliqué |
