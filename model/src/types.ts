import type { PlDataTableStateV2 } from "@platforma-sdk/model";

/**
 * Workflow inputs (projected from BlockData by the args lambda; validated there).
 * Populated with the anchored result-pool selection in plan Task 5.
 */
export type BlockArgs = Record<string, never>;

/** Unified persisted UI + grid state. */
export type BlockData = {
  tableState: PlDataTableStateV2; // PlAgDataTableV2 grid state (UI-only, never projected to args)
};
