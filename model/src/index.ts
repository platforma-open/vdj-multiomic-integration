import type {
  InferOutputsType,
  PFrameHandle,
  RenderCtx,
  SUniversalPColumnId,
} from "@platforma-sdk/model";
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
  heatmapState: {
    title: "Antigen binding heatmap",
    template: "heatmap" as const,
    currentTab: null,
  },
  bindingBubbleState: {
    title: "Antigen binding profile",
    template: "bubble" as const,
    currentTab: null,
  },
  distributionState: {
    title: "Reactivity distribution",
    template: "bins" as const,
    currentTab: null,
    // Green bars to match the other views (default template fill would otherwise be white).
    layersSettings: { bins: { fillColor: "#99E099" } },
  },
}));

// Clonotype × antigen matrix columns ([scClonotypeKey, featureId]) — the binding heatmap + bubble.
const MATRIX_COLS = ["pl7.app/feature/clonotypeFraction", "pl7.app/feature/clonotypeUmiCount"];
// Per-clonotype scalar columns ([scClonotypeKey]) — the reactivity histogram.
const SCALAR_COLS = ["pl7.app/vdj/restrictionIndex", "pl7.app/vdj/breadth"];
// The clonotype axis label column (pl7.app/label -> "C-XXXXX"). Included in the graph frames so
// GraphMaker relabels the scClonotypeKey axis to the readable clone id instead of the raw content
// hash. createPFrameForGraphs pulls label columns in automatically via getRelatedColumns, but it
// enumerates the result pool and hangs on the upstream Samples & Data FASTQ dataset (see the frame
// comment below), so we add the label column by hand from our own exportFrame'd table.
const LABEL_COL = "pl7.app/label";

// Shared resolver for the GraphMaker outputs below: the clonotypeTable PColumns filtered to a
// name-set, or undefined while the frame is still computing (getPColumns() throws mid-compute, which
// the catch maps to "not ready" — withStatus + GraphMaker render that as a loading state).
function graphCols(ctx: RenderCtx<BlockArgs, BlockData>, names: string[]) {
  try {
    return ctx.outputs
      ?.resolve("clonotypeTable")
      ?.getPColumns()
      ?.filter((c) => names.includes(c.spec.name));
  } catch {
    return undefined;
  }
}

// The value columns plus the clonotype label (so GraphMaker relabels the scClonotypeKey axis),
// assembled into a PFrame via ctx.createPFrame (own columns only — avoids the result-pool enumeration
// that hangs on the upstream Samples & Data FASTQ dataset). undefined unless at least one value column
// (not just the label) is present.
function graphPFrame(
  ctx: RenderCtx<BlockArgs, BlockData>,
  names: string[],
): PFrameHandle | undefined {
  try {
    const cols = ctx.outputs
      ?.resolve("clonotypeTable")
      ?.getPColumns()
      ?.filter((c) => names.includes(c.spec.name) || c.spec.name === LABEL_COL);
    // require at least one value column, not just the label
    if (cols === undefined || !cols.some((c) => names.includes(c.spec.name))) return undefined;
    return ctx.createPFrame(cols);
  } catch {
    return undefined;
  }
}

export const platforma = BlockModelV3.create(dataModel)
  .args<BlockArgs>((data) => {
    if (!data.datasetRef) throw new Error("Select a VDJ single-cell dataset");
    if (!data.featureColumnId)
      throw new Error("Select the Feature Integration per-cell feature column");
    return {
      datasetRef: data.datasetRef,
      featureColumnId: data.featureColumnId,
      // gexColumnId + expressionMethod feed the optional per-gene expression output (A-0019),
      // activated via the GEX controls in the settings modal. See workflow/src/aggregate.tpl.tengo.
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
  // Optional per-cell gene-expression count matrix, discovered via the cell linker; set by the GEX
  // dropdown in the settings modal to drive the per-gene expression output (A-0019).
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
  // Graph frames, split by axis structure. A GraphMaker chart tabulates its whole PFrame into one
  // PTable, so a frame must be axis-homogeneous: the [scClonotypeKey, featureId] matrix feeds the
  // heatmap + bubble; the [scClonotypeKey] scalars feed the reactivity histogram. Mixing axes (or the
  // [scClonotypeKey, geneId] expression column) in one frame has no valid join.
  //
  // Source columns from the exportFrame'd `clonotypeTable` output, NOT the raw `propertiesPf`: only the
  // exportFrame'd frame materializes the column blobs, so ctx.createPFrame can read their blob info.
  // Building from raw `propertiesPf` throws "Key not found ctl/file/blobInfo" (verified). ctx.createPFrame
  // (own columns only) also avoids createPFrameForGraphs's result-pool enumeration, which blocks forever
  // on the upstream Samples & Data FASTQ File-dataset (the same pool-enumeration trap clonotypeTable
  // avoids with maxHops:0). getPColumns() throws while the frame is still computing; the catch maps that
  // to "not ready" (undefined), which withStatus + GraphMaker render as a loading state.
  .outputWithStatus("bindingPf", (ctx) => graphPFrame(ctx, MATRIX_COLS))
  .output("bindingPCols", (ctx) => graphCols(ctx, MATRIX_COLS))
  .outputWithStatus("distributionPf", (ctx) => graphPFrame(ctx, SCALAR_COLS))
  .output("distributionPCols", (ctx) => graphCols(ctx, SCALAR_COLS))
  .title(() => "VDJ Multiomic Integration")
  .sections(() => [
    { type: "link" as const, href: "/" as const, label: "Table" },
    { type: "link" as const, href: "/heatmap" as const, label: "Binding heatmap" },
    { type: "link" as const, href: "/bubble" as const, label: "Binding profile" },
    { type: "link" as const, href: "/distribution" as const, label: "Reactivity" },
  ])
  .done();

export type BlockOutputs = InferOutputsType<typeof platforma>;
