---
'@platforma-open/milaboratories.vdj-multiomic-integration.workflow': patch
'@platforma-open/milaboratories.vdj-multiomic-integration.aggregate-clonotypes': patch
---

Make the per-clonotype antigen metrics control-aware. The negative control is now removed entirely from the restriction index, antigen breadth, per-antigen fraction columns, and the dominant call — it is not a callable antigen, and previously it silently counted as one (inflating breadth, diluting the restriction index, appearing as its own fraction column, and able to win the dominant call). Feature Integration marks the control on the feature axis (`pl7.app/feature/negativeControl`); this block discovers that marker and drops the control before any metric is computed. Off-targets are unaffected — they stay in the metrics and are only barred from winning the dominant call. With no control designated the output is unchanged.
