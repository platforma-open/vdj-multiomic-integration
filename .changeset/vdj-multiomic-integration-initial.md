---
'@platforma-open/milaboratories.vdj-multiomic-integration': minor
'@platforma-open/milaboratories.vdj-multiomic-integration.model': minor
'@platforma-open/milaboratories.vdj-multiomic-integration.ui': minor
'@platforma-open/milaboratories.vdj-multiomic-integration.workflow': minor
'@platforma-open/milaboratories.vdj-multiomic-integration.aggregate-clonotypes': minor
---

Initial release of the VDJ Multiomic Integration block. Aggregates per-cell data onto VDJ clonotypes and emits the categorical per-clonotype properties via the dominant-category rule: the dominant antigen (from Feature Integration per-cell assignments) and, when a cell-type annotation is provided, the dominant cell type. Reuses the dataset's scClonotypeKey axis verbatim and pools cells across samples (no sample axis). Numerical properties (per-feature fractions/UMI counts, restriction index, breadth, gene expression) are deferred to a follow-up.
