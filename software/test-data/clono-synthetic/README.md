# clono-synthetic test bed

Tiny, hand-designed fixtures for the per-clonotype aggregation tests. Committed (not generated at
test time) and excluded from ruff. Regenerate with `python generate.py`.

- `features.csv` — per-cell feature UMI counts (`sampleId,cellId,feature,umiCount`), i.e. what Feature
  Integration's abundance column materializes to.
- `linker.csv` — the cell↔clonotype linker (`sampleId,cellId,scClonotypeKey`), i.e. mixcr-clonotyping's
  `pl7.app/sc/cellLinker`.

Designed so per-clonotype metrics are hand-computable and exercise cross-sample pooling + the
inner-join drop:

| clonotype | cells | pooled counts | fractions | RI | breadth@0.0 | dominant |
|-----------|-------|---------------|-----------|----|-----|----------|
| **C1** | cellA(s1) + cellB(s2) | AGX 8, BGX 2 | 0.8 / 0.2 | ≈0.278 | 2 | AGX |
| **C2** | cellC(s1) | AGX 5 | 1.0 | 1.0 | 1 | AGX |

`cellZ` (s1) appears in `features.csv` but **not** in `linker.csv`, so it is dropped by the inner
join (spec A-0022 / DP-4) — the result must contain only C1 and C2.
