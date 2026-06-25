# VDJ Multiomic Integration

Aggregates per-cell multiomic data onto VDJ clonotypes. Given a VDJ dataset (with its single-cell
linker) and the per-cell feature columns produced by the **Feature Integration** block, it groups
cells by clonotype across all samples and computes, per clonotype:

- per-feature fractions and counts,
- the **restriction index** (entropy-based focus of the clonotype's feature distribution),
- **breadth** (number of features present above a threshold),
- the **dominant feature** (dominant-category rule),

and, optionally, when gene-expression and cell-annotation columns are selected:

- per-gene mean / max expression,
- the dominant cell-type annotation.

Aggregation pools cells across samples — the outputs carry no sample axis and are keyed only by the
VDJ clonotype.
