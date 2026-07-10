# @platforma-open/milaboratories.vdj-multiomic-integration

## 1.1.0

### Minor Changes

- 3f279d1: Add two per-clonotype visualization views alongside the results table: a clonotype × antigen binding heatmap and a distribution histogram of a per-clonotype metric. Both plot columns the aggregation already emits, so there are no workflow computation changes.

  Each view is a GraphMaker section over a self-contained PFrame split by axis structure: the heatmap uses the per-(clonotype, antigen) matrix frame and the histogram uses the per-clonotype scalar frame. The graph frames are built from the block's own exported clonotype columns (sourced from the `exportFrame`'d results table so the column blobs are materialized) and never enumerate the result pool — this keeps them self-contained and avoids hanging on unrelated upstream datasets.

- 3356f1c: Enrich the per-clonotype results table with readable clonotype identity. The opaque `scClonotypeKey` was the only clonotype identifier shown; now the workflow pulls, from the VDJ dataset under the anchor, the clonotype label (`pl7.app/label`, "C-XXXXX") plus the primary heavy/light CDR3 aa and V/J gene columns, and joins them on the shared `scClonotypeKey` axis. These carry import-vdj-data's own labels and table visibility. The table stays self-contained (no discovery / `maxHops` change in the model), so the fix adds no result-pool enumeration.
- dad651d: Initial release of the VDJ Multiomic Integration block. Aggregates per-cell data onto VDJ clonotypes and emits the categorical per-clonotype properties via the dominant-category rule: the dominant antigen (from Feature Integration per-cell assignments) and, when a cell-type annotation is provided, the dominant cell type. Reuses the dataset's scClonotypeKey axis verbatim and pools cells across samples (no sample axis). Numerical properties (per-feature fractions/UMI counts, restriction index, breadth, gene expression) are deferred to a follow-up.
- d0719df: Emit the per-clonotype numerical antigen-binding profile: restriction index, breadth, per-feature fraction columns, and the advanced feature UMI count matrix. These were already computed by the aggregator but gated out under the initial categorical-only scope; phase 2 un-gates the workflow imports. Per-gene expression and any per-clonotype specificity score remain deferred. Restriction index and breadth carry `pl7.app/isScore` with `pl7.app/score/rankingOrder: "decreasing"` (and no default cutoff), so downstream lead-selection can rank clonotypes on them.
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
