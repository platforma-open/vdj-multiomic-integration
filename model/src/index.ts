import type {
  InferOutputsType,
  PFrameHandle,
  RenderCtx,
  SUniversalPColumnId,
} from "@platforma-sdk/model";
import {
  AccessorColumnsProvider,
  BlockModelV3,
  createPlDataTableStateV2,
  createPlDataTableV3,
  DataModelBuilder,
  isPColumnSpec,
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

// Per-cell categorical annotation columns: a 2-axis String PColumn carrying a pl7.app/sc/cellId axis.
// Discovered by shape, not by name, so any annotation from the gene-expression pipeline is offered —
// not only cell type. The block's own feature columns (pl7.app/feature/*) are excluded: those are
// integrated as features. NB: the axis-order check is intentionally order-agnostic (`.some`), so a
// column specced [cellId, sampleId] is admitted as well as [sampleId, cellId]. This is safe because the
// per-cell CSV export in aggregate.tpl.tengo (buildCellCsv) maps axis headers BY SEMANTIC NAME, not by
// position — a reversed-axis column still exports the cellId/sampleId columns under the right headers
// and joins. Do NOT tighten this to a positional check without also revisiting that export.
function discoverAnnotationOptions(
  ctx: RenderCtx<BlockArgs, BlockData>,
): { label: string; value: SUniversalPColumnId }[] {
  const opts = ctx.resultPool.getOptions(
    (spec) =>
      isPColumnSpec(spec) &&
      spec.valueType === "String" &&
      spec.axesSpec.length === 2 &&
      spec.axesSpec.some((a) => a.name === "pl7.app/sc/cellId") &&
      !spec.name.startsWith("pl7.app/feature/"),
  );
  return (opts ?? []).map((o) => ({
    label: o.label,
    value: JSON.stringify(o.ref) as SUniversalPColumnId,
  }));
}

const DOMINANCE_FLOOR = 0.5; // the dominance threshold is user-adjustable down to 0.5, never lower

const dataModel = new DataModelBuilder().from<BlockData>("v1").init(() => ({
  integrations: [],
  customBlockLabel: "",
  defaultBlockLabel: "",
  tableState: createPlDataTableStateV2(),
  // Property heatmap defaults to the clustered template with column mean-normalization.
  heatmapState: {
    title: "Feature heatmap",
    template: "heatmapClustered" as const,
    currentTab: null,
    layersSettings: {
      heatmapClustered: {
        normalizationDirection: "column",
        normalizationMethod: "meanNormalization",
        dendrogramX: false,
        dendrogramY: false,
      },
    },
  },
  distributionState: {
    title: "Feature distribution",
    template: "bins" as const,
    currentTab: null,
    // Green bars to match the other views (default template fill would otherwise be white).
    layersSettings: { bins: { fillColor: "#99E099" } },
  },
  compositionState: {
    title: "Annotation composition",
    template: "bar" as const,
    currentTab: null,
    layersSettings: {},
    axesSettings: {
      other: {
        facetSharedBy: "y" as const,
        showLegend: false,
      },
    },
  },
}));

// Clonotype × antigen matrix columns ([scClonotypeKey, featureId]) — the property heatmap.
const MATRIX_COLS = ["pl7.app/feature/clonotypeFraction", "pl7.app/feature/clonotypeUmiCount"];
// Per-clonotype scalar columns ([scClonotypeKey]) — the distribution histogram.
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
    const integrations = data.integrations ?? [];
    if (integrations.length === 0)
      throw new Error("Add at least one integration (a feature or an annotation)");
    // A card added but not yet given a selection gates the run (mirrors Lead Selection's half-filled card).
    if (integrations.some((i) => !i.ref || !i.kind))
      throw new Error("Every added card must select a data type");
    // Project the generic integration list to the workflow: the single feature-kind integration is the
    // feature matrix; every annotation-kind integration is folded on independently (dominant-category).
    // The workflow carries one featureColumnId, so more than one feature card is rejected rather than
    // silently dropped.
    const features = integrations.filter((i) => i.kind === "feature");
    if (features.length > 1) throw new Error("Only one feature integration is supported");
    const feature = features[0];
    // Single presence cutoff from the feature integration, applied to every feature (0 when absent).
    const presenceThreshold = Math.min(1, Math.max(0, feature?.presenceThreshold ?? 0));
    // Per-integration dominance thresholds, clamped to the 0.5 floor.
    const dom = (i?: { dominanceThreshold?: number }) =>
      Math.max(DOMINANCE_FLOOR, i?.dominanceThreshold ?? 0.6);
    const annotations = integrations
      .filter((i) => i.kind === "annotation")
      .map((i) => ({
        ref: i.ref as SUniversalPColumnId,
        dominanceThreshold: dom(i),
        label: i.label ?? "Annotation",
      }));
    return {
      datasetRef: data.datasetRef,
      featureColumnId: feature?.ref,
      featureLabel: feature?.label,
      featureDominanceThreshold: dom(feature),
      annotations,
      presenceThreshold,
      // Off-target designation (F2), carried on the feature card. Projected only when both are set, so the
      // dominant-feature call is unchanged otherwise (the workflow leaves the rule alone on empty).
      ...(feature?.offtargetProperty &&
      feature.offtargetValues &&
      feature.offtargetValues.length > 0
        ? { offtargetProperty: feature.offtargetProperty, offtargetValues: feature.offtargetValues }
        : {}),
      // Block label -> workflow trace label (finalize). Changing it re-runs so the new label is baked
      // into the exported columns' provenance.
      customBlockLabel: data.customBlockLabel ?? "",
      defaultBlockLabel: data.defaultBlockLabel ?? "",
    };
  })
  // VDJ single-cell dataset anchor: columns keyed on [sampleId, scClonotypeKey] flagged as anchors
  .output("datasetOptions", (ctx) =>
    ctx.resultPool.getOptions([
      {
        axes: [{ name: "pl7.app/sampleId" }, { name: "pl7.app/vdj/scClonotypeKey" }],
        annotations: { "pl7.app/isAnchor": "true" },
      },
    ]),
  )
  // The per-cell columns the user can add as integrations. Feature-kind is the featureId-axis UMI matrix
  // (one column carrying every feature); annotation-kind is any [sampleId, cellId] String column. Values
  // are global hit ids (workflow-resolvable); `kind` routes each to the right aggregation.
  .output("integrationOptions", (ctx) => [
    ...discoverLinkedOptions(ctx, "pl7.app/feature/umiCount").map((o) => ({
      ...o,
      kind: "feature" as const,
    })),
    ...discoverAnnotationOptions(ctx).map((o) => ({ ...o, kind: "annotation" as const })),
  ])
  // Off-target designation options (F2). Feature Integration imports every extra tag-CSV column as a
  // per-feature property (pl7.app/feature/property), carrying the original header in the domain
  // (pl7.app/feature/propertyName) and its distinct values in the pl7.app/discreteValues annotation. Read
  // those from the pool SPECS (no data needed) so the UI can offer the property dropdown + a value
  // multi-select for the off-target designation. Empty until a Feature Integration upstream has run.
  .output(
    "offtargetPropertyOptions",
    (ctx): { propertyName: string; label: string; values: string[] }[] => {
      const byProp = new Map<string, { label: string; values: string[] }>();
      for (const entry of ctx.resultPool.getSpecs().entries) {
        const spec = entry.obj;
        if (!isPColumnSpec(spec) || spec.name !== "pl7.app/feature/property") continue;
        const propName = spec.domain?.["pl7.app/feature/propertyName"];
        if (!propName) continue;
        const rawValues = spec.annotations?.["pl7.app/discreteValues"];
        let values: string[] = [];
        if (rawValues) {
          // Boundary parse: discreteValues comes from another block's spec in the pool. A single
          // malformed annotation must not throw and take down the whole options output (and with it
          // the off-target dropdown for the block) — degrade that one property to no preset values.
          try {
            const parsed = JSON.parse(rawValues);
            if (Array.isArray(parsed)) values = parsed.map(String);
          } catch {
            values = [];
          }
        }
        const label = spec.annotations?.["pl7.app/label"] ?? propName;
        byProp.set(propName, { label, values });
      }
      return [...byProp.entries()].map(([propertyName, v]) => ({
        propertyName,
        label: v.label,
        values: v.values,
      }));
    },
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
  // blocks forever on the upstream Samples&Data FASTQ File-dataset. `sources: [AccessorColumnsProvider(acc)]`
  // confines column + label discovery to this block's columns; maxHops:0 disables linker traversal
  // since the PFrame is self-contained. retentive avoids blanking the grid on recompute; withStatus
  // feeds PlAgDataTableV2 the OutputWithStatus envelope. NB: under maxHops:0 the scClonotypeKey /
  // featureId axis labels resolve only from within our PFrame — verify label rendering in the
  // backend test.
  .output(
    "clonotypeTable",
    (ctx) => {
      const acc = ctx.outputs?.resolve("clonotypeTable");
      if (acc === undefined) return undefined;
      const snapshots = AccessorColumnsProvider(acc).getColumns();
      if (snapshots.length === 0) return undefined;
      // Anchor on any value-bearing column — discovery is axis-driven, only its axesSpec matters.
      const anchorSpec = (
        snapshots.find((s) => s.getSpec().name !== "pl7.app/label") ?? snapshots[0]
      ).getSpec();
      return createPlDataTableV3(ctx, {
        columns: {
          sources: [AccessorColumnsProvider(acc)],
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
  // property heatmap; the [scClonotypeKey] scalars feed the distribution histogram. Mixing axes in one
  // frame has no valid join.
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
  // Composition stacked bar: the pre-aggregated (annotation, category) -> clonotype-count frame, resolved
  // from the workflow's separate compositionTable output (axes [annotation, category], NOT per-clonotype).
  .outputWithStatus("compositionPf", (ctx) => {
    try {
      const cols = ctx.outputs?.resolve("compositionTable")?.getPColumns();
      if (!cols || cols.length === 0) return undefined;
      return ctx.createPFrame(cols);
    } catch {
      return undefined;
    }
  })
  .output("compositionPCols", (ctx) => {
    try {
      return ctx.outputs?.resolve("compositionTable")?.getPColumns();
    } catch {
      return undefined;
    }
  })
  .title(() => "Clonotype Multiomic Integration")
  // Subtitle = the block label: the user's override, else the input-derived default (the selected
  // dataset's label, synced into data by the UI). The same label feeds the trace (args), so distinct
  // VDJM instances are distinguishable both here and in downstream Lead Selection column labels.
  .subtitle((ctx) => ctx.data.customBlockLabel || ctx.data.defaultBlockLabel)
  // The plot pages read the feature binding profile (the [scClonotypeKey, featureId] fraction matrix and
  // the restriction-index / breadth scalars). Show them only once that profile is computed, so a run with
  // no feature integration (or before the first run) surfaces just Main.
  .sections((ctx) => {
    const hasProfile = (() => {
      try {
        return !!ctx.outputs
          ?.resolve("clonotypeTable")
          ?.getPColumns()
          ?.some((c) => c.spec.name === "pl7.app/feature/clonotypeFraction");
      } catch {
        return false;
      }
    })();
    // Composition appears when an annotation has been integrated (its aggregated frame exists).
    const hasComposition = (() => {
      try {
        const c = ctx.outputs?.resolve("compositionTable")?.getPColumns();
        return !!c && c.length > 0;
      } catch {
        return false;
      }
    })();
    return [
      { type: "link" as const, href: "/" as const, label: "Main" },
      ...(hasProfile
        ? [
            { type: "link" as const, href: "/heatmap" as const, label: "Feature Heatmap" },
            {
              type: "link" as const,
              href: "/distribution" as const,
              label: "Feature Distribution",
            },
          ]
        : []),
      ...(hasComposition
        ? [
            {
              type: "link" as const,
              href: "/composition" as const,
              label: "Annotation Composition",
            },
          ]
        : []),
    ];
  })
  .done();

export type BlockOutputs = InferOutputsType<typeof platforma>;
export type { BlockArgs, BlockData, IntegrationEntry, IntegrationKind } from "./types";
// Re-exported for the UI package (which depends on this model package, not @platforma-sdk/model directly).
export { createPlDataTableStateV2 } from "@platforma-sdk/model";
export type { PlRef } from "@platforma-sdk/model";
