---
'@platforma-open/milaboratories.vdj-multiomic-integration.workflow': patch
'@platforma-open/milaboratories.vdj-multiomic-integration.model': minor
'@platforma-open/milaboratories.vdj-multiomic-integration.ui': minor
'@platforma-open/milaboratories.vdj-multiomic-integration': minor
---

Add three per-clonotype visualization views alongside the results table: a clonotype × antigen binding heatmap, a binding-profile bubble plot (bubble size = UMI count, color = within-clonotype fraction), and a reactivity-distribution histogram of the restriction index. All plot columns the aggregation already emits, so there are no workflow computation changes.

Each view is a GraphMaker section over a self-contained PFrame split by axis structure: the heatmap and bubble share the per-(clonotype, antigen) matrix frame, and the histogram uses the per-clonotype scalar frame. The graph frames are built from the block's own exported clonotype columns (sourced from the `exportFrame`'d results table so the column blobs are materialized) and never enumerate the result pool — this keeps them self-contained and avoids hanging on unrelated upstream datasets.
