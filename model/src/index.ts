import type { InferOutputsType, RenderCtx, SUniversalPColumnId } from "@platforma-sdk/model";
import {
  BlockModelV3,
  createPlDataTableStateV2,
  createPlDataTableV3,
  DataModelBuilder,
  OutputColumnProvider,
} from "@platforma-sdk/model";
import type { BlockArgs, BlockData } from "./types";

// Discover a per-cell column (by name) and offer it as a dropdown option whose value is the column's
// GLOBAL id — the only form the workflow's bundleBuilder.addSingle resolves standalone (global-ref
// branch → bquery.resolve, data included).
//
// Why getOptions and not the anchored discovery: the feature/annotation columns are per-cell
// [sampleId, cellId, …], reachable from the clonotype anchor only across the cell linker. The anchored
// discoveries (getCanonicalOptions / findColumnVariants "enrichment") DO reach the column but emit an
// ANCHORED id, which the workflow routes to bquery.anchoredQuery — and anchoredQuery does not traverse
// the linker, so the column comes back unresolved (spec+data undefined). getOptions returns the
// column's resolvable global PlRef directly. Trade-off: it is not dataset-scoped (whole result pool),
// which is fine while there is a single upstream producer per column type.
function discoverLinkedOptions(
  ctx: RenderCtx<BlockArgs, BlockData>,
  columnName: string,
): { label: string; value: SUniversalPColumnId }[] {
  const opts = ctx.resultPool.getOptions([{ name: columnName }]);
  return (opts ?? []).map((o) => ({
    label: o.label,
    value: JSON.stringify(o.ref) as SUniversalPColumnId,
  }));
}

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
      // DORMANT (deferred per-gene expression): gexColumnId + expressionMethod feed the GEX
      // expression output, which phase 2 does not emit. Kept in args so re-activation restores the
      // UI GEX control without reshaping args. See workflow/src/aggregate.tpl.tengo.
      gexColumnId: data.gexColumnId,
      annotationColumnId: data.annotationColumnId,
      // canonicalize + clamp to the 0.5 floor (A-0012)
      dominanceThreshold: Math.max(DOMINANCE_FLOOR, data.dominanceThreshold ?? 0.6),
      // presenceThreshold now feeds the emitted breadth column; default 0 = count features with any signal.
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
  // Feature Integration per-cell UMI-count column, discovered via the cell linker from the dataset
  // anchor. Value is the global hit id (workflow-resolvable) — see discoverLinkedOptions.
  .output("featureOptions", (ctx) =>
    ctx.data.datasetRef ? discoverLinkedOptions(ctx, "pl7.app/feature/umiCount") : [],
  )
  // DORMANT (v1 = categorical only): GEX drives the deferred numerical expression output; no UI
  // control currently sets gexColumnId. Kept so the numerical-properties plan restores the GEX
  // dropdown without re-adding this query.
  // Optional per-cell gene-expression count matrix
  .output("gexOptions", (ctx) =>
    ctx.data.datasetRef ? discoverLinkedOptions(ctx, "pl7.app/rna-seq/countMatrix") : [],
  )
  // Optional per-cell cell-type annotation
  .output("annotationOptions", (ctx) =>
    ctx.data.datasetRef ? discoverLinkedOptions(ctx, "pl7.app/rna-seq/cellType") : [],
  )
  // True while the main run is executing (no output/context field settled yet) — drives the block
  // spinner via the app.ts progress callback. The Python aggregation is a long-running (16 GiB) step.
  .output("isRunning", (ctx) => ctx.outputs?.getIsReadyOrError() === false)
  // Per-clonotype results table. Resolves the workflow's clonotypeTable PFrame; undefined until the
  // workflow emits it, so the UI guards it with v-if.
  //
  // Use the self-contained discovery form of createPlDataTableV3 with `sources` scoped to our OWN
  // exported PFrame (mirrors feature-integration / 3d-structure-prediction). The array-columns form
  // runs discoverLabelColumnVariants, which enumerates the ENTIRE result pool to find axis labels and
  // blocks forever on the upstream Samples&Data FASTQ File-dataset. `sources: [OutputColumnProvider(acc)]`
  // confines column + label discovery to this block's columns; maxHops:0 disables linker traversal
  // since the PFrame is self-contained. retentive avoids blanking the grid on recompute; withStatus
  // feeds PlAgDataTableV2 the OutputWithStatus envelope. NB: under maxHops:0 the scClonotypeKey /
  // featureId axis labels resolve only from within our PFrame — verify label rendering in the Task-7
  // backend test.
  .output(
    "clonotypeTable",
    (ctx) => {
      const acc = ctx.outputs?.resolve("clonotypeTable");
      if (acc === undefined) return undefined;
      const snapshots = new OutputColumnProvider(acc).getAllColumns();
      if (snapshots.length === 0) return undefined;
      // Anchor on any value-bearing column — discovery is axis-driven, only its axesSpec matters.
      const anchorSpec = (snapshots.find((s) => s.spec.name !== "pl7.app/label") ?? snapshots[0])
        .spec;
      return createPlDataTableV3(ctx, {
        columns: {
          sources: [new OutputColumnProvider(acc)],
          anchors: { main: anchorSpec },
          selector: { mode: "enrichment", maxHops: 0 },
        },
        tableState: ctx.data.tableState,
      });
    },
    { retentive: true, withStatus: true },
  )
  .title(() => "VDJ Multiomic Integration")
  .sections(() => [{ type: "link" as const, href: "/" as const, label: "Main" }])
  .done();

export type BlockOutputs = InferOutputsType<typeof platforma>;
