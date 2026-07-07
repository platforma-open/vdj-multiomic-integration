---
'@platforma-open/milaboratories.vdj-multiomic-integration.ui': patch
'@platforma-open/milaboratories.vdj-multiomic-integration.model': patch
'@platforma-open/milaboratories.vdj-multiomic-integration.workflow': patch
---

v1 finalization:

- Add a "Presence threshold (breadth)" numeric control (0.0–1.0, default 0.0) to the settings modal, wired to the existing `presenceThreshold` arg. Breadth was previously fixed at "count features with any signal" with no way to change it.
- Activate per-gene expression (A-0019): add a "Gene expression (optional)" column dropdown + an "Expression aggregation" (mean/max) selector to the settings modal. The workflow + Python already computed and could emit per-gene mean/max expression per clonotype; it was inert only because no UI set `gexColumnId`. Selecting a GEX column now emits the `pl7.app/rna-seq/clonotypeExpression` (clonotype × gene) matrix. Updated the now-stale "dormant" comments in the model + workflow.
