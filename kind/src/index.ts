import { assertParamsObject, defineBlockKind } from "@platforma-sdk/block-kind";
import type { PlRef } from "@platforma-sdk/model";
import { isPlRef } from "@platforma-sdk/model";
import { name, version } from "../package.json" with { type: "json" };

/**
 * This block's init-params contract: the VDJ single-cell dataset a new instance integrates onto.
 * The integration cards, labels and view states stay out; the UI owns and defaults them.
 *
 * `datasetRef` is optional: a block whose dataset is not picked yet holds `undefined`, and the
 * projection hands that back untouched.
 */
export type BlockParams = {
  datasetRef?: PlRef;
};

/**
 * The same contract at runtime, for params that arrive from a template file. A readable
 * `{ block, name }` reference is expanded to a full `PlRef` before this runs.
 */
function parseInitializationParams(value: unknown): BlockParams {
  assertParamsObject(value);

  const { datasetRef } = value;
  if (datasetRef !== undefined && !isPlRef(datasetRef)) {
    throw new Error(
      "'datasetRef' must be a reference to an upstream column, written as { block, name }.",
    );
  }

  return { datasetRef };
}

// Identity (`name`/`version`) comes from this package's own `package.json`, so
// the on-wire `{name}@{version}` reference can never drift from what npm
// publishes; the bundler inlines the JSON import.
export const kind = defineBlockKind<BlockParams>({
  name,
  version,
  parseInitializationParams,
});
