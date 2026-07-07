---
'@platforma-open/milaboratories.vdj-multiomic-integration.workflow': patch
'@platforma-open/milaboratories.vdj-multiomic-integration.model': minor
'@platforma-open/milaboratories.vdj-multiomic-integration.ui': minor
'@platforma-open/milaboratories.vdj-multiomic-integration': minor
---

Add three per-clonotype visualization views alongside the results table: a clonotype × antigen binding heatmap, a binding-profile bubble plot (bubble size = UMI count, color = within-clonotype fraction), and a reactivity-distribution histogram of the restriction index. Each is a separate block section backed by GraphMaker over a single per-clonotype PFrame; all plot the columns the aggregation already emits, so no workflow computation changes. The workflow now also surfaces the per-clonotype PFrame as a model-readable output (`propertiesPf`) to feed the graphs.
