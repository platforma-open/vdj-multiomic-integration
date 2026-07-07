---
'@platforma-open/milaboratories.vdj-multiomic-integration.aggregate-clonotypes': minor
'@platforma-open/milaboratories.vdj-multiomic-integration.workflow': minor
'@platforma-open/milaboratories.vdj-multiomic-integration.model': minor
'@platforma-open/milaboratories.vdj-multiomic-integration.ui': minor
'@platforma-open/milaboratories.vdj-multiomic-integration': minor
---

Make the per-clonotype binding profile usable in Lead Selection, and rework Settings around per-antigen configuration.

Emissions for downstream lead selection:
- The dominant antigen column now carries `pl7.app/discreteValues` (the antigens present, plus "ambiguous") alongside `isDiscreteFilter`, so Lead Selection offers it as a multi-select filter — previously it was emitted as a discrete filter with no value list, so no selector appeared.
- The within-clonotype fraction is now also emitted as one scalar p-column per antigen (keyed on the clonotype, antigen in the domain), so each antigen's fraction is a per-clonotype numeric filter downstream. The per-(clonotype, antigen) fraction matrix is retained for the in-block heatmap only; the advanced UMI-count matrix is unchanged.

Both need the antigen set, which is data-derived, so the aggregation template is split: the Python emits the sorted distinct feature names, and a `finalize` child template awaits that value and builds the per-antigen columns and the dominant-antigen `discreteValues`.

Settings and views:
- Picking the VDJ dataset auto-discovers the feature/antigen, gene-expression and cell-type columns from the shared sample + cell barcode (the manual per-column dropdowns are gone).
- A per-antigen card list: each antigen has a hide toggle (removes it from the in-block plots only) and a presence threshold — the minimum within-clonotype fraction for that antigen to count as present, which drives breadth and the dominant-antigen call (restriction index is unaffected).
- Tabs renamed: Table → Main, Reactivity → Distribution (default binned value is now breadth), Binding Heatmap → Property Heatmap (defaults to the clustered heatmap with column mean-normalization); the Binding Profile tab is removed.
