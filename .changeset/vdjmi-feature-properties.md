---
"@platforma-open/milaboratories.vdj-multiomic-integration.workflow": patch
---

Discover Feature Integration's per-feature property columns and carry them onto the per-clonotype export. Feature Integration imports every extra tag-CSV column (beyond the mapped barcode-sequence and feature-name roles) as a `pl7.app/feature/property` column keyed on the feature axis — for example antigen species (human / cyno). The workflow now registers the selected feature/antigen column as an anchor and pulls every property column whose feature axis matches it, then re-emits each verbatim onto the `clonotypeProperties` export keyed on the shared feature axis. Downstream Lead Selection can therefore group and filter features by property (e.g. pool all human against all cyno antigens). Generic over an arbitrary number and naming of properties (no hardcoded schema); a no-op when the panel CSV carried no extra columns or when no feature integration is present.
