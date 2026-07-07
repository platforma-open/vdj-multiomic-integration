<script setup lang="ts">
import type { PredefinedGraphOption } from "@milaboratories/graph-maker";
import { GraphMaker } from "@milaboratories/graph-maker";
import { computed } from "vue";
import { useApp } from "../app";

const app = useApp();

// Per-clonotype distribution histogram. Defaults the binned value to breadth (the number of antigens a
// clonotype binds); the restriction index is in the same frame, so the user can switch to it from the
// GraphMaker controls.
const defaultOptions = computed((): PredefinedGraphOption<"histogram">[] | null => {
  const pCols = app.model.outputs.distributionPCols;
  if (!pCols || pCols.length === 0) return null;

  const breadth = pCols.find((p) => p.spec.name === "pl7.app/vdj/breadth");
  const restrictionIndex = pCols.find((p) => p.spec.name === "pl7.app/vdj/restrictionIndex");
  const metric = breadth ?? restrictionIndex;
  if (!metric) return null;

  return [{ inputName: "value", selectedSource: metric.spec }];
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
