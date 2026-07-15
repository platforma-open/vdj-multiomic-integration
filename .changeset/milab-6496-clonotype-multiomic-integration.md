---
"@platforma-open/milaboratories.vdj-multiomic-integration": minor
"@platforma-open/milaboratories.vdj-multiomic-integration.model": minor
"@platforma-open/milaboratories.vdj-multiomic-integration.ui": minor
"@platforma-open/milaboratories.vdj-multiomic-integration.workflow": patch
"@platforma-open/milaboratories.vdj-multiomic-integration.aggregate-clonotypes": patch
---

Clonotype Multiomic Integration — pilot finishing (BEAM in-vivo).

Analysis / functionality:

- Per-antigen fraction columns plus a per-clonotype dominant-antigen / breadth / restriction-index call and a per-clonotype antigen breakdown — each antigen fraction is its own rankable and filterable column at Lead Selection.
- Discover Feature Barcode Profiling's per-feature property columns and carry them verbatim onto the per-clonotype export (`clonotypeProperties`, keyed on the shared feature axis), so Lead Selection can group and filter by property (for example human vs cyno antigens). Generic over an arbitrary number and naming of properties; a no-op when the panel carried no extra columns or no feature integration is present.
- Off-target-aware dominant call plus a "cross-reactive" label, behind a future-release flag and hidden this pilot: with no designation set, output is unchanged.

Housekeeping / UX:

- Rename the block display title to "Clonotype Multiomic Integration" and match the workflow trace-label fallback to the new name (the trace-step type is unchanged).
- Add the `multiomics` tag.
- Add tooltips to the presence and dominance thresholds.
- Remove middot/bullet separators from clonotype labels, the breakdown output, and the default subtitle (derived from the selected dataset's label; a manually typed subtitle is left untouched).
- Remove dead code paths never wired into the UI: the gene-expression per-clonotype aggregation and the per-antigen presence-threshold override (both unreachable in v1). The single global presence-threshold cutoff is unchanged, so there is no user-facing behavior change.
