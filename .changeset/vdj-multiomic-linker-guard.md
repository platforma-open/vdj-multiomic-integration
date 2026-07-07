---
'@platforma-open/milaboratories.vdj-multiomic-integration.workflow': patch
---

Fail with a clear message when the selected VDJ dataset has more than one clonotype grouping.

VDJ Multiomic Integration v1 aggregates over a single clonotype grouping, resolved via the dataset's single cell linker. When V(D)J data is imported with multiple chain sets, the dataset carries one grouping — and one cell linker — per set, and the linker resolution previously failed with the opaque backend message "single resolve has 2 or more results". The workflow now probes the linker count under the dataset anchor before aggregation and stops with an actionable message (re-import with a single chain set, or run one grouping at a time), before the heavy per-clonotype aggregation runs.
