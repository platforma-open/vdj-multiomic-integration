# Aggregation contract — VDJ Multiomic Integration

Design note for the per-clonotype aggregation (plan Task 0). Resolves the join/group contract and
the two open decision points (DP-4, DP-5) before the workflow (Tasks 3-4) is written.

> **Operator sign-off: PENDING.** The resolutions below are the recommended conservative defaults.
> They are already reflected in the Python software (Task 2) and will be used by the workflow unless
> the operator overrides them.

## Join / group contract (verified)

The block joins the per-cell columns to the VDJ dataset's **cell linker** and groups by clonotype.

- **Cell linker** — `pl7.app/sc/cellLinker` (valueType `Int`, annotation `pl7.app/isLinkerColumn: "true"`),
  axes `[pl7.app/sampleId, pl7.app/sc/cellId, pl7.app/vdj/scClonotypeKey]`, partitioned by sampleId
  (from `blocks/mixcr-clonotyping/workflow/src/calculate-export-specs.lib.tengo:1160-1191`).
- **Join key:** `[pl7.app/sampleId, pl7.app/sc/cellId]` — shared between the linker and every per-cell
  input (feature UMI counts, GEX count matrix, cell-type annotation).
- **Group key:** `pl7.app/vdj/scClonotypeKey` — the linker's 3rd axis, **reused verbatim** on every
  output column so they join back to the existing clonotype table. No new axis is minted.
- **No sample axis on outputs** (invariant A-0005): cells are pooled across samples before grouping.
- Per-cell inputs share `pl7.app/sc/cellId` as their cell axis: feature column (A-0010), GEX
  `pl7.app/rna-seq/countMatrix`, annotation `pl7.app/rna-seq/cellType`. *(GEX/annotation cell-axis
  identity asserted from the plan's shared-facts table; to be re-verified against live specs in the
  Task-7 integration test.)*

## DP-4 — missing-data representation

**Decision: inner-join drop for matrix entries; explicit null for scalar per-clonotype properties.**

- A cell with no linker row (not assigned to any clonotype) is **dropped** — it contributes to no
  clonotype. (Already implemented: `aggregate_clonotypes.py` inner-joins on `[sampleId, cellId]`.)
- A clonotype with no signal for a given feature simply has **no row** in the feature
  fraction/count matrices (sparse, drop) — not a zero row.
- Scalar per-clonotype properties (dominant feature, dominant cell type) emit **null** when there is
  no signal, consistent with the dominant-category rule's null state (A-0012).
- `restrictionIndex` for a single-feature clonotype is `1.0`; for an empty clonotype it is `nan`
  (matches `compartment_analysis.py`). Breadth is `0` when nothing clears the presence threshold.

Spec A-0022 defers the formal treatment; this note records the working resolution.

## DP-5 — `pl7.app/isScore` on `restrictionIndex`

**Decision: OFF by default.** `pl7.app/vdj/restrictionIndex` is emitted with label "Restriction index"
and `pl7.app/format: ".3f"`, but **without** `pl7.app/isScore: "true"`.

Rationale: clonotype-distribution sets `isScore` on its analogous column
(`process.tpl.tengo:228-243`), but there is no published validation that the restriction index is a
meaningful cross-clonotype score here. Per the spec STATUS backlog this is an operator call; default
off avoids over-claiming. Flip to on with a one-line annotation change if the operator decides it
should rank.

## Consequences for the workflow (Tasks 3-4)

- The workflow materializes the feature column + the linker (and optionally GEX + annotation) to
  CSVs via `csvFileBuilder`, runs `aggregate_clonotypes.py`, and imports the per-clonotype columns
  reusing the `scClonotypeKey` axis verbatim.
- The linker is the dataset's intrinsic column — resolved workflow-side from the dataset anchor (the
  model does not pass a separate linker id; see the Task-5 note in the plan `.tasks.json`).
