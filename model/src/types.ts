import type { PlDataTableStateV2, PlRef, SUniversalPColumnId } from "@platforma-sdk/model";

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
  presenceThreshold: number; // spec A-0013, default 0.0
  expressionMethod: "mean" | "max"; // spec A-0019, default mean
};

/** Unified persisted UI + grid state (designed on the UI's terms). */
export type BlockData = {
  datasetRef?: PlRef;
  featureColumnId?: SUniversalPColumnId;
  gexColumnId?: SUniversalPColumnId;
  annotationColumnId?: SUniversalPColumnId;
  dominanceThreshold: number;
  presenceThreshold: number;
  expressionMethod: "mean" | "max";
  tableState: PlDataTableStateV2; // PlAgDataTableV2 grid state (UI-only, never projected to args)
};
