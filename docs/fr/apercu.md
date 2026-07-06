# Apercu

SimParc-R Simulator permet d'executer des simulations de parcs residentiels a grande echelle en utilisant un flux OpenStudio-HPXML.

## Ce que fait le simulateur

1. Lit un fichier CSV de parc de batiments.
2. Valide et pretraite les entrees selon les contraintes HPXML.
3. Applique au besoin des scenarios de mesures decrits dans `project.yaml`.
4. Execute les simulations en parallele avec OpenStudio.
5. Produit des sorties structurees pour l'analyse.

## Modules principaux

- `local.py`: point d'entree en ligne de commande.
- `project.yaml`: configuration de simulation.
- `preprocessing.py`: pretraitement des donnees d'entree.
- `upgrading.py`: filtres et transformations de mesures.
- `building.py`: generation des workflows par batiment.
- `postprocessing.py`: post-traitement et jeux de donnees de sortie.

## Flux typique

1. Configurer les parametres dans `project.yaml`.
2. Lancer un lot de simulation.
3. Explorer les jeux de donnees produits dans `results/`.
