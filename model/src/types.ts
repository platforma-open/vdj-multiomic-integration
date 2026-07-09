import type { GraphMakerState } from "@milaboratories/graph-maker";
import type { PlDataTableStateV2, PlRef, SUniversalPColumnId } from "@platforma-sdk/model";

/** The kind of per-cell integration, classified from the picked column's shape on add:
 * - "feature"    : a per-cell PColumn with a featureId axis ([sampleId, cellId, featureId], numeric)
 *                  -> per-feature fractions, restriction index, breadth, dominant feature.
 * - "annotation" : a per-cell categorical scalar ([sampleId, cellId], String)
 *                  -> dominant-category label per clonotype. */
export type IntegrationKind = "feature" | "annotation";

/** One integration card. Added empty (only `id`), then the user picks a per-cell column in the card,
 * which snapshots `ref` / `kind` / `label`. `ref` is the resolvable global column id; `kind` is the
 * column shape ("feature" / "annotation"); `label` is a display snapshot. `presenceThreshold` (feature
 * kind only) is the within-clonotype fraction a feature must exceed to count as bound, applied to every
 * feature; it feeds breadth and the dominant call. `dominanceThreshold` is the share the top category
 * must reach to be this integration's dominant call (else "ambiguous"), floor 0.5. A card with no `ref`
 * is incomplete: args rejects it so the run is gated until it is completed or removed. */
export type IntegrationEntry = {
  id: string; // stable UI id (list ordering / keying); never projected to args
  ref?: SUniversalPColumnId; // the picked per-cell column (global, workflow-resolvable); unset until picked
  kind?: IntegrationKind; // the picked column's shape; unset until picked
  label?: string; // display snapshot (UI only); unset until picked
  presenceThreshold?: number; // feature kind only; within-clonotype fraction to count as bound
  dominanceThreshold?: number; // share the top category must reach to be dominant (else ambiguous), floor 0.5
};

/**
 * Workflow inputs (projected from BlockData by the args lambda; validated there).
 * The anchored column ids are stored together with `datasetRef` so the anchor map
 * ({ main: datasetRef }) can be rebuilt verbatim on every render. `datasetRef` is the VDJ single-cell
 * dataset that owns the cell-to-clonotype linker; the linker column is resolved workflow-side from it.
 */
export type BlockArgs = {
  datasetRef: PlRef; // VDJ single-cell dataset (the cellLinker anchor)
  // The first feature-kind integration's per-cell UMI-count column (spec A-0010), when one is present.
  // Optional: the block also runs on VDJ + annotations with no features.
  featureColumnId?: SUniversalPColumnId;
  gexColumnId?: SUniversalPColumnId; // gene-expression count matrix (spec A-0019)
  annotationColumnId?: SUniversalPColumnId; // the first annotation-kind integration's column (spec A-0020)
  featureDominanceThreshold: number; // dominance threshold for the dominant-feature call (spec A-0012, floor 0.5)
  annotationDominanceThreshold: number; // dominance threshold for the dominant-annotation call (spec A-0012/A-0020, floor 0.5)
  presenceThreshold: number; // within-clonotype fraction a feature must exceed to count as bound (feeds breadth + dominant-feature); applied to every feature
  expressionMethod: "mean" | "max"; // gene-expression aggregation method (spec A-0019)
  // Block label -> the pl7.app/trace step label on every emitted column, so downstream (Lead Selection)
  // can tell which VDJM instance a column came from. customBlockLabel is the user's override; defaultBlockLabel
  // is the input-derived fallback (the selected dataset's label).
  customBlockLabel: string;
  defaultBlockLabel: string;
};

/** Unified persisted UI + grid state (designed on the UI's terms). */
export type BlockData = {
  datasetRef?: PlRef;
  // The per-cell integrations the user has added (generic add-list). Array so the UI owns display order;
  // the args lambda projects it to the workflow's column slots. Per-integration thresholds live on each entry.
  integrations: IntegrationEntry[];
  // Editable block label (the subtitle) + its input-derived default; both feed the trace label (args).
  // defaultBlockLabel is synced from the selected dataset's label by the UI (a tolerated block-label hairpin).
  customBlockLabel: string;
  defaultBlockLabel: string;
  tableState: PlDataTableStateV2; // PlAgDataTableV2 grid state (UI-only, never projected to args)
  // GraphMaker view state, one per plot page (UI-only, never projected to args).
  heatmapState: GraphMakerState; // clonotype x feature property heatmap
  distributionState: GraphMakerState; // restriction-index / breadth histogram
};
