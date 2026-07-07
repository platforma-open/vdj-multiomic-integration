---
'@platforma-open/milaboratories.vdj-multiomic-integration.workflow': patch
---

Stop the exported per-clonotype properties frame from re-exporting the borrowed VDJ identity columns.

The aggregation borrows readable clonotype-identity columns (label, primary heavy/light CDR3 aa, V/J genes) from the upstream VDJ dataset purely to enrich this block's own results table. Those columns were being published in `exports.clonotypeProperties`, but they already live in the result pool under the same `scClonotypeKey` axis (from import-vdj-data). A downstream block that anchors the clonotype dataset (e.g. antibody/TCR lead selection) then saw two copies of each and failed with `header 'cdr3Sequence.Heavy' is not unique`.

The aggregation now builds two frames from the same results: a display frame (own columns + borrowed identity) that feeds the in-block table and plots, and an export frame (own columns only) that is the pool-published `clonotypeProperties`. Downstream anchoring is now collision-free.
