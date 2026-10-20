---
"@platforma-open/milaboratories.vdj-multiomic-integration": minor
"@platforma-open/milaboratories.vdj-multiomic-integration.kind": minor
"@platforma-open/milaboratories.vdj-multiomic-integration.model": minor
"@platforma-open/milaboratories.vdj-multiomic-integration.ui": minor
"@platforma-open/milaboratories.vdj-multiomic-integration.workflow": minor
---

Update the SDK and accept a subset filter (e.g. a Repertoire Labeling label or Lead Selection picks) with the VDJ single-cell dataset. The dataset list is built with buildDatasetOptions (requireEnrichments: false). The subset restricts the cell linker before the aggregation, so only its clonotypes and their cells are integrated: per-clonotype values are the same as in a full-data run, while the annotation composition, the per-feature fraction columns and the value lists of the dominant-feature and dominant-annotation filters cover only what the subset contains. Columns computed on a subset carry pl7.app/inputSubset in their domain and a trace rooted in the subset, so their labels name it; the default subtitle names the subset too. The results table and plots show only the subset's clonotypes. Unfiltered runs are unchanged.
