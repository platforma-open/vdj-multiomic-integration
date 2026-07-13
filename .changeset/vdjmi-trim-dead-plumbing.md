---
"@platforma-open/milaboratories.vdj-multiomic-integration.model": patch
"@platforma-open/milaboratories.vdj-multiomic-integration.workflow": patch
"@platforma-open/milaboratories.vdj-multiomic-integration.aggregate-clonotypes": patch
---

Remove dead code paths that were never wired into the block UI: the gene-expression per-clonotype aggregation (gexColumnId / expressionMethod, the --gex-csv / --expression-method plumbing) and the per-antigen presence-threshold override (the --presence-thresholds map). Both were unreachable in v1. The single global presence-threshold cutoff is unchanged, so there is no user-facing behavior change.
