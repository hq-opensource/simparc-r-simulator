# Aperçu

SimParc-R Simulator permet d'exécuter des simulations de parcs résidentiels à grande échelle en utilisant un flux OpenStudio-HPXML.

## Ce que fait le simulateur

1. Lit un fichier CSV de parc de bâtiments.
2. Valide et prétraite les entrées selon les contraintes HPXML.
3. Applique au besoin des scénarios de mesures décrits dans `project.yaml`.
4. Exécute les simulations en parallèle avec OpenStudio.
5. Produit des sorties structurées pour l'analyse.

## Modules principaux

- `local.py`: point d'entrée en ligne de commande.
- `project.yaml`: configuration de simulation.
- `preprocessing.py`: prétraitement des données d'entrée.
- `upgrading.py`: filtres et transformations de mesures.
- `building.py`: génération des workflows par bâtiment.
- `postprocessing.py`: post-traitement et jeux de données de sortie.

## Flux typique

1. Configurer les paramètres dans `project.yaml`.
2. Lancer un lot de simulation.
3. Explorer les jeux de données produits dans `results/`.
