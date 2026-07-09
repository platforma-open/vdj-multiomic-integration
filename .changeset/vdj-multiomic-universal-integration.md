---
'@platforma-open/milaboratories.vdj-multiomic-integration.aggregate-clonotypes': minor
'@platforma-open/milaboratories.vdj-multiomic-integration.workflow': minor
'@platforma-open/milaboratories.vdj-multiomic-integration.model': minor
'@platforma-open/milaboratories.vdj-multiomic-integration.ui': minor
'@platforma-open/milaboratories.vdj-multiomic-integration': minor
---

Make the block a generic per-cell integrator instead of a fixed antigen + cell-type block.

- Inputs are chosen as an "Add data" card list: pick the VDJ dataset, then add any per-cell column. Columns are classified by shape into a feature (UMI-count matrix) or an annotation (categorical, e.g. cell type or cluster id), so any gene-expression annotation is offered.
- The feature integration is optional: the block runs on VDJ plus annotations alone.
- Multiple annotations are supported, each folded on independently (dominant-category) and emitted as its own column, named from its source, with its own dominance threshold.
- New "Annotation Composition" view: one faceted barplot per annotation, counts pre-aggregated so it scales independently of clonotype count.
- Feature heatmap and distribution views appear only when feature data is computed.
- Upgraded onto the latest SDK / structurer layout.
