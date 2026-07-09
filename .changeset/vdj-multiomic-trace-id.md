---
'@platforma-open/milaboratories.vdj-multiomic-integration.workflow': patch
---

Stamp this block's instance id on its provenance trace step.

The aggregation's own `pl7.app/trace` step previously carried no `id`, unlike every upstream step (Samples & Data, dataset, Feature Integration). It now records `wf.blockId()`, so each VDJ Multiomic Integration instance's lineage is distinguishable in downstream provenance.
