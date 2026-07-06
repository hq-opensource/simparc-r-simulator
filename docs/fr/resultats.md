# Resultats et sorties

Les sorties de simulation sont ecrites dans `results/`.

## Artefacts principaux

- Dossiers par batiment (journaux et sorties de workflow).
- `results_job0.json.gz`: resume compact des sorties de simulation.
- `metadata.parquet/`: jeu de metadonnees partitionne.
- `timeseries.parquet/`: jeu de series temporelles partitionne (si active).
- `errors.parquet/`: jeu partitionne des echecs de simulation.

## Parcours d'analyse conseille

1. Examiner `errors.parquet/` pour identifier les cas en echec.
2. Consulter `metadata.parquet/` pour les metriques annuelles et le contexte par batiment.
3. Utiliser `timeseries.parquet/` pour les analyses temporelles (pointes, charges, flexibilite).

## Remarque

Les lots volumineux peuvent generer un volume de donnees important. Prevoir un stockage adapte.
