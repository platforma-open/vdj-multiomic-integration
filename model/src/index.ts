import type { InferOutputsType } from "@platforma-sdk/model";
import {
  ArrayColumnProvider,
  BlockModelV3,
  createPlDataTableStateV2,
  createPlDataTableV3,
  DataModelBuilder,
} from "@platforma-sdk/model";
import type { BlockArgs, BlockData } from "./types";

const DOMINANCE_FLOOR = 0.5; // spec A-0012: threshold is user-adjustable down to 0.5, never lower

const dataModel = new DataModelBuilder().from<BlockData>("v1").init(() => ({
  dominanceThreshold: 0.6,
  presenceThreshold: 0.0,
  expressionMethod: "mean" as const,
  tableState: createPlDataTableStateV2(),
}));

export const platforma = BlockModelV3.create(dataModel)
  .args<BlockArgs>((data) => {
    if (!data.datasetRef) throw new Error("Select a VDJ single-cell dataset");
    if (!data.featureColumnId)
      throw new Error("Select the Feature Integration per-cell feature column");
    return {
      datasetRef: data.datasetRef,
      featureColumnId: data.featureColumnId,
      gexColumnId: data.gexColumnId,
      annotationColumnId: data.annotationColumnId,
      // canonicalize + clamp to the 0.5 floor (A-0012)
      dominanceThreshold: Math.max(DOMINANCE_FLOOR, data.dominanceThreshold ?? 0.6),
      presenceThreshold: data.presenceThreshold ?? 0.0,
      expressionMethod: data.expressionMethod ?? "mean",
    };
  })
  // VDJ single-cell dataset anchor: columns keyed on [sampleId, scClonotypeKey] flagged as anchors
  .output("datasetOptions", (ctx) =>
    ctx.resultPool.getOptions(
      [
        {
          axes: [{ name: "pl7.app/sampleId" }, { name: "pl7.app/vdj/scClonotypeKey" }],
          annotations: { "pl7.app/isAnchor": "true" },
        },
      ],
      { refsWithEnrichments: true },
    ),
  )
  // Feature Integration per-cell UMI-count column, discovered relative to the dataset anchor
  .output("featureOptions", (ctx) =>
    ctx.data.datasetRef
      ? ctx.resultPool.getCanonicalOptions({ main: ctx.data.datasetRef }, [
          { name: "pl7.app/feature/umiCount" },
        ])
      : [],
  )
  // Optional per-cell gene-expression count matrix
  .output("gexOptions", (ctx) =>
    ctx.data.datasetRef
      ? ctx.resultPool.getCanonicalOptions({ main: ctx.data.datasetRef }, [
          { name: "pl7.app/rna-seq/countMatrix" },
        ])
      : [],
  )
  // Optional per-cell cell-type annotation
  .output("annotationOptions", (ctx) =>
    ctx.data.datasetRef
      ? ctx.resultPool.getCanonicalOptions({ main: ctx.data.datasetRef }, [
          { name: "pl7.app/rna-seq/cellType" },
        ])
      : [],
  )
  // Per-clonotype results table (latest builder: createPlDataTableV3). Resolves the workflow's
  // clonotypeTable PFrame; undefined until the aggregation workflow (plan Tasks 3-4) emits it, so
  // the UI guards it with v-if.
  .outputWithStatus("clonotypeTable", (ctx) => {
    const cols = ctx.outputs?.resolve("clonotypeTable")?.getPColumns();
    if (!cols) return undefined;
    return createPlDataTableV3(ctx, {
      columns: new ArrayColumnProvider(cols)
        .getAllColumns()
        .map((column) => ({ column, isPrimary: true })),
      tableState: ctx.data.tableState,
    });
  })
  .title(() => "VDJ Multiomic Integration")
  .sections(() => [{ type: "link" as const, href: "/" as const, label: "Main" }])
  .done();

export type BlockOutputs = InferOutputsType<typeof platforma>;
