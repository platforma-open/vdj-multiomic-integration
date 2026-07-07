---
'@platforma-open/milaboratories.vdj-multiomic-integration': minor
'@platforma-open/milaboratories.vdj-multiomic-integration.workflow': minor
'@platforma-open/milaboratories.vdj-multiomic-integration.model': patch
---

Emit the per-clonotype numerical antigen-binding profile (A-0011 v1.1 / A-0015): restriction index, breadth, per-feature fraction columns, and the advanced feature UMI count matrix. These were already computed by the aggregator but gated out under the initial categorical-only scope; phase 2 un-gates the workflow imports. Per-gene expression and any per-clonotype specificity score remain deferred. Restriction index and breadth carry `pl7.app/isScore` with `pl7.app/score/rankingOrder: "decreasing"` (and no default cutoff), so downstream lead-selection can rank clonotypes on them (aggregation-contract DP-5, signed off ON 2026-07-06).
