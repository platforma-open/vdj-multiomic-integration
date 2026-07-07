import type { GraphMakerState } from "@milaboratories/graph-maker";
import type { PlDataTableStateV2, PlRef, SUniversalPColumnId } from "@platforma-sdk/model";

/** Per-antigen configuration, keyed in BlockData by antigen name.
 * `presenceThreshold` is the per-antigen presence/binding cutoff (a within-clonotype fraction 0..1):
 * an antigen counts as present for a clonotype only when its fraction exceeds this. It drives breadth
 * and the dominant-antigen call, so it IS projected to args (changing it re-runs the block).
 * `hidden` removes the antigen from the in-block plots ONLY — pure view state, never projected to args. */
export type AntigenSetting = {
  presenceThreshold?: number;
  hidden?: boolean;
};

/**
 * Workflow inputs (projected from BlockData by the args lambda; validated there).
 * The anchored column ids are stored together with `datasetRef` so the anchor map
 * ({ main: datasetRef }) can be rebuilt verbatim on every render — harness p-columns
 * Pattern B. `datasetRef` is the VDJ single-cell dataset that owns the cell↔clonotype
 * linker; the linker column itself is resolved workflow-side from this anchor.
 */
export type BlockArgs = {
  datasetRef: PlRef; // VDJ single-cell dataset (the cellLinker anchor)
  featureColumnId: SUniversalPColumnId; // Feature Integration per-cell UMI-count column (spec A-0010)
  gexColumnId?: SUniversalPColumnId; // optional gene-expression count matrix (spec A-0019)
  annotationColumnId?: SUniversalPColumnId; // optional cell-type annotation (spec A-0020)
  dominanceThreshold: number; // spec A-0012, default 0.6, floor 0.5
  presenceThresholds: Record<string, number>; // per-antigen presence cutoffs (feature name -> fraction); default-valued entries omitted
  expressionMethod: "mean" | "max"; // spec A-0019, default mean
  // Block label -> the pl7.app/trace step label on every emitted column, so downstream (Lead Selection)
  // can tell which VDJM instance a column came from. customBlockLabel is the user's override; defaultBlockLabel
  // is the input-derived fallback (the selected dataset's label).
  customBlockLabel: string;
  defaultBlockLabel: string;
};

/** Unified persisted UI + grid state (designed on the UI's terms). */
export type BlockData = {
  datasetRef?: PlRef;
  featureColumnId?: SUniversalPColumnId;
  gexColumnId?: SUniversalPColumnId;
  annotationColumnId?: SUniversalPColumnId;
  dominanceThreshold: number;
  // Per-antigen settings keyed by antigen name; auto-populated from the discovered antigens. Threshold
  // feeds args (re-run); `hidden` is plots-only (UI). Keyed by name so a toggle survives antigen-set churn.
  antigenSettings: Record<string, AntigenSetting>;
  expressionMethod: "mean" | "max";
  // Editable block label (the subtitle) + its input-derived default; both feed the trace label (args).
  // defaultBlockLabel is synced from the selected dataset's label by the UI (a tolerated block-label hairpin).
  customBlockLabel: string;
  defaultBlockLabel: string;
  tableState: PlDataTableStateV2; // PlAgDataTableV2 grid state (UI-only, never projected to args)
  // GraphMaker view state, one per plot page (UI-only, never projected to args).
  heatmapState: GraphMakerState; // clonotype × antigen property heatmap
  distributionState: GraphMakerState; // restriction-index / breadth histogram
};
