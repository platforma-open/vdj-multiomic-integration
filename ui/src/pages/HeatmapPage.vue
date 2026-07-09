<script setup lang="ts">
import type { PredefinedGraphOption } from "@milaboratories/graph-maker";
import { GraphMaker } from "@milaboratories/graph-maker";
import { computed } from "vue";
import { useApp } from "../app";

const app = useApp();

// Clonotype × antigen property heatmap: y = clonotype, x = antigen, color = within-clonotype fraction.
// The block default template is the clustered heatmap with column mean-normalization (set in the model's
// heatmapState init — the BEAM6 reference configuration). The fraction column is keyed on
// [scClonotypeKey, featureId] (axesSpec[0], axesSpec[1]).
const defaultOptions = computed((): PredefinedGraphOption<"heatmap">[] | null => {
  const pCols = app.model.outputs.bindingPCols;
  if (!pCols || pCols.length === 0) return null;

  const fraction = pCols.find((p) => p.spec.name === "pl7.app/feature/clonotypeFraction");
  if (!fraction || !fraction.spec.axesSpec || fraction.spec.axesSpec.length < 2) return null;

  const options: PredefinedGraphOption<"heatmap">[] = [
    { inputName: "x", selectedSource: fraction.spec.axesSpec[1] },
    { inputName: "y", selectedSource: fraction.spec.axesSpec[0] },
    { inputName: "value", selectedSource: fraction.spec },
  ];
  return options;
});
</script>

<template>
  <GraphMaker
    v-model="app.model.data.heatmapState"
    chart-type="heatmap"
    :p-frame="app.model.outputs.bindingPf"
    :default-options="defaultOptions"
  />
</template>
