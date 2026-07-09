# VDJ Multiomic Integration

Aggregates single-cell measurements onto your antibody and TCR clonotypes, linking each clonotype to
what was measured in its cells.

Start from a single-cell VDJ dataset and add the per-cell data you want to bring onto your clonotypes:
antigen binding from the Feature Integration block, and categorical cell annotations from your
single-cell gene-expression analysis (such as a cell type or cluster assignment). The block pools every
cell of a clonotype across all samples and summarizes each clonotype.

From antigen binding, for every clonotype you get:

- how strongly it binds each antigen,
- how many antigens it binds,
- how focused its binding is on a single antigen,
- the antigen it binds most strongly.

From each cell annotation, you get the value that dominates the clonotype, plus an overview of how your
clonotypes are distributed across its categories.

You can combine antigen binding with annotations, or use annotations on their own. Results are reported
per clonotype, pooled across all samples, and can be picked up by downstream blocks such as Sequence
Space and Lead Selection.
