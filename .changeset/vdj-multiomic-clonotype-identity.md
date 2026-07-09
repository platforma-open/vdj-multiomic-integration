---
'@platforma-open/milaboratories.vdj-multiomic-integration.workflow': minor
'@platforma-open/milaboratories.vdj-multiomic-integration': minor
---

Enrich the per-clonotype results table with readable clonotype identity. The opaque `scClonotypeKey` was the only clonotype identifier shown; now the workflow pulls, from the VDJ dataset under the anchor, the clonotype label (`pl7.app/label`, "C-XXXXX") plus the primary heavy/light CDR3 aa and V/J gene columns, and joins them on the shared `scClonotypeKey` axis. These carry import-vdj-data's own labels and table visibility. The table stays self-contained (no discovery / `maxHops` change in the model), so the fix adds no result-pool enumeration.
