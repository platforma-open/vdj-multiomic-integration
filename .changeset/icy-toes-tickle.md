---
"@platforma-open/milaboratories.vdj-multiomic-integration.model": patch
"@platforma-open/milaboratories.vdj-multiomic-integration.workflow": patch
"@platforma-open/milaboratories.vdj-multiomic-integration": patch
---

Remove refsWithEnrichments so the block no longer goes stale when upstream blocks are reordered. Export the within-clonotype feature fraction matrix (clonotypeFraction) so it is available to downstream blocks (e.g. Graph Maker box plots).
