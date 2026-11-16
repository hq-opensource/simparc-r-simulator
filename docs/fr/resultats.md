# Résultats et sorties

Les sorties de simulation sont écrites dans `results/`.

## Artefacts principaux

- Dossiers par bâtiment (journaux et sorties de workflow).
- `results_job0.json.gz`: résumé compact des sorties de simulation.
- `metadata.parquet/`: jeu de métadonnées partitionné.
- `timeseries.parquet/`: jeu de séries temporelles partitionné (si activé).
- `errors.parquet/`: jeu partitionné des échecs de simulation.

## Parcours d'analyse conseillé

1. Examiner `errors.parquet/` pour identifier les cas en échec.
2. Consulter `metadata.parquet/` pour les métriques annuelles et le contexte par bâtiment.
3. Utiliser `timeseries.parquet/` pour les analyses temporelles (pointes, charges, flexibilité).

## Remarque

Les lots volumineux peuvent générer un volume de données important. Prévoir un stockage adapté.
