# @platforma-open/milaboratories.vdj-multiomic-integration.ui

## 1.1.2

### Patch Changes

- Updated dependencies [cd34950]
  - @platforma-open/milaboratories.vdj-multiomic-integration.model@1.1.2

## 1.1.1

### Patch Changes

- 64bffa8: SDK Update
- Updated dependencies [64bffa8]
  - @platforma-open/milaboratories.vdj-multiomic-integration.model@1.1.1

## 1.1.0

### Minor Changes

- 3f279d1: Add two per-clonotype visualization views alongside the results table: a clonotype × antigen binding heatmap and a distribution histogram of a per-clonotype metric. Both plot columns the aggregation already emits, so there are no workflow computation changes.

  Each view is a GraphMaker section over a self-contained PFrame split by axis structure: the heatmap uses the per-(clonotype, antigen) matrix frame and the histogram uses the per-clonotype scalar frame. The graph frames are built from the block's own exported clonotype columns (sourced from the `exportFrame`'d results table so the column blobs are materialized) and never enumerate the result pool — this keeps them self-contained and avoids hanging on unrelated upstream datasets.

- dad651d: Initial release of the VDJ Multiomic Integration block. Aggregates per-cell data onto VDJ clonotypes and emits the categorical per-clonotype properties via the dominant-category rule: the dominant antigen (from Feature Integration per-cell assignments) and, when a cell-type annotation is provided, the dominant cell type. Reuses the dataset's scClonotypeKey axis verbatim and pools cells across samples (no sample axis). Numerical properties (per-feature fractions/UMI counts, restriction index, breadth, gene expression) are deferred to a follow-up.
- 3f8c116: Make the per-clonotype binding profile usable in Lead Selection, and rework Settings around per-antigen configuration.

  Emissions for downstream lead selection:

  - The dominant antigen column now carries `pl7.app/discreteValues` (the antigens present, plus "ambiguous") alongside `isDiscreteFilter`, so Lead Selection offers it as a multi-select filter — previously it was emitted as a discrete filter with no value list, so no selector appeared.
  - The within-clonotype fraction is now also emitted as one scalar p-column per antigen (keyed on the clonotype, antigen in the domain), so each antigen's fraction is a per-clonotype numeric filter downstream. The per-(clonotype, antigen) fraction matrix is retained for the in-block heatmap only; the advanced UMI-count matrix is unchanged.

  Both need the antigen set, which is data-derived, so the aggregation template is split: the Python emits the sorted distinct feature names, and a `finalize` child template awaits that value and builds the per-antigen columns and the dominant-antigen `discreteValues`.

  Settings and views:

  - Picking the VDJ dataset auto-discovers the feature/antigen, gene-expression and cell-type columns from the shared sample + cell barcode (the manual per-column dropdowns are gone).
  - A per-antigen card list: each antigen has a hide toggle (removes it from the in-block plots only) and a presence threshold — the minimum within-clonotype fraction for that antigen to count as present, which drives breadth and the dominant-antigen call (restriction index is unaffected).
  - Views: the clonotype × antigen heatmap tab is titled "Property Heatmap" and defaults to the clustered heatmap with column mean-normalization; the histogram tab is titled "Distribution" and bins breadth by default; the results tab is titled "Main".
  - The borrowed per-chain (heavy/light) CDR3 aa / V / J gene identity columns default to hidden in the results table; the clonotype label and this block's own properties lead.
  - Editable block-label subtitle: defaults to the selected dataset's label and feeds the `pl7.app/trace` label on every emitted column, so distinct VDJM instances are distinguishable in the block header and in downstream column provenance.

- eb70755: Make the block a generic per-cell integrator instead of a fixed antigen + cell-type block.

  - Inputs are chosen as an "Add data" card list: pick the VDJ dataset, then add any per-cell column. Columns are classified by shape into a feature (UMI-count matrix) or an annotation (categorical, e.g. cell type or cluster id), so any gene-expression annotation is offered.
  - The feature integration is optional: the block runs on VDJ plus annotations alone.
  - Multiple annotations are supported, each folded on independently (dominant-category) and emitted as its own column, named from its source, with its own dominance threshold.
  - New "Annotation Composition" view: one faceted barplot per annotation, counts pre-aggregated so it scales independently of clonotype count.
  - Feature heatmap and distribution views appear only when feature data is computed.
  - Upgraded onto the latest SDK / structurer layout.

### Patch Changes

- 749105c: v1 finalization:

  - Add a "Presence threshold (breadth)" numeric control (0.0–1.0, default 0.0) to the settings modal, wired to the existing `presenceThreshold` arg. Breadth was previously fixed at "count features with any signal" with no way to change it.
  - Activate per-gene expression: add a "Gene expression (optional)" column dropdown + an "Expression aggregation" (mean/max) selector to the settings modal. The workflow + Python already computed and could emit per-gene mean/max expression per clonotype; it was inert only because no UI set `gexColumnId`. Selecting a GEX column now emits the `pl7.app/rna-seq/clonotypeExpression` (clonotype × gene) matrix. Updated the now-stale "dormant" comments in the model + workflow.

- Updated dependencies [3f279d1]
- Updated dependencies [dad651d]
- Updated dependencies [d0719df]
- Updated dependencies [3f8c116]
- Updated dependencies [eb70755]
- Updated dependencies [749105c]
  - @platforma-open/milaboratories.vdj-multiomic-integration.model@1.1.0
