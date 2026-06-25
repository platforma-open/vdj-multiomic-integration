import type { InferOutputsType } from "@platforma-sdk/model";
import { BlockModelV3, createPlDataTableStateV2, DataModelBuilder } from "@platforma-sdk/model";
import type { BlockArgs, BlockData } from "./types";

const dataModel = new DataModelBuilder()
  .from<BlockData>("v1")
  .init(() => ({ tableState: createPlDataTableStateV2() }));

// Scaffold model. The anchored result-pool inputs (VDJ dataset anchor + feature/GEX/annotation
// pickers via getCanonicalOptions) and the per-clonotype results table land in plan Tasks 5-6.
export const platforma = BlockModelV3.create(dataModel)
  .args((): BlockArgs => ({}))
  .title(() => "VDJ Multiomic Integration")
  .sections(() => [{ type: "link" as const, href: "/" as const, label: "Main" }])
  .done();

export type BlockOutputs = InferOutputsType<typeof platforma>;
