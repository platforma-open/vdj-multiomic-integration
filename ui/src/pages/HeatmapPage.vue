<script setup lang="ts">
import type { PredefinedGraphOption } from "@milaboratories/graph-maker";
import { GraphMaker } from "@milaboratories/graph-maker";
import { computed } from "vue";
import { useApp } from "../app";

const app = useApp();

// Clonotype × antigen binding heatmap: y = clonotype, x = antigen, color = within-clonotype fraction.
// The fraction column is keyed on [scClonotypeKey, featureId] (axesSpec[0], axesSpec[1]).
const defaultOptions = computed((): PredefinedGraphOption<"heatmap">[] | null => {
  const pCols = app.model.outputs.graphsPCols;
  if (!pCols || pCols.length === 0) return null;

  const fraction = pCols.find((p) => p.spec.name === "pl7.app/feature/clonotypeFraction");
  if (!fraction || !fraction.spec.axesSpec || fraction.spec.axesSpec.length < 2) return null;

  return [
    { inputName: "x", selectedSource: fraction.spec.axesSpec[1] },
    { inputName: "y", selectedSource: fraction.spec.axesSpec[0] },
    { inputName: "value", selectedSource: fraction.spec },
  ];
});
</script>

<template>
  <GraphMaker
    v-model="app.model.data.heatmapState"
    chart-type="heatmap"
    :p-frame="app.model.outputs.graphsPf"
    :default-options="defaultOptions"
  />
</template>
