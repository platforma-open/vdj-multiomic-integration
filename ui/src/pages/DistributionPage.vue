<script setup lang="ts">
import type { PredefinedGraphOption } from "@milaboratories/graph-maker";
import { GraphMaker } from "@milaboratories/graph-maker";
import { computed } from "vue";
import { useApp } from "../app";

const app = useApp();

// Repertoire-level reactivity distribution: histogram of the per-clonotype restriction index (0..1,
// mono- vs poly-reactivity). Breadth is in the same frame, so the user can switch the binned value to
// it from the GraphMaker controls.
const defaultOptions = computed((): PredefinedGraphOption<"histogram">[] | null => {
  const pCols = app.model.outputs.distributionPCols;
  if (!pCols || pCols.length === 0) return null;

  const ri = pCols.find((p) => p.spec.name === "pl7.app/vdj/restrictionIndex");
  if (!ri) return null;

  return [{ inputName: "value", selectedSource: ri.spec }];
});
</script>

<template>
  <GraphMaker
    v-model="app.model.data.distributionState"
    chart-type="histogram"
    :p-frame="app.model.outputs.distributionPf"
    :default-options="defaultOptions"
  />
</template>
