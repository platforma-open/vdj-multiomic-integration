<script setup lang="ts">
import type { PredefinedGraphOption } from "@milaboratories/graph-maker";
import { GraphMaker } from "@milaboratories/graph-maker";
import { computed } from "vue";
import { useApp } from "../app";

const app = useApp();

// Clonotype × antigen bubble: y = clonotype, x = antigen, bubble size = UMI count, color = fraction.
// Two encodings (magnitude + normalized share) make a focused shortlist more scannable than the flat
// heatmap. Both matrix columns are keyed on [scClonotypeKey, featureId] (axesSpec[0], axesSpec[1]).
const defaultOptions = computed((): PredefinedGraphOption<"bubble">[] | null => {
  const pCols = app.model.outputs.bindingPCols;
  if (!pCols || pCols.length === 0) return null;

  const umi = pCols.find((p) => p.spec.name === "pl7.app/feature/clonotypeUmiCount");
  const fraction = pCols.find((p) => p.spec.name === "pl7.app/feature/clonotypeFraction");
  if (!umi || !fraction || !umi.spec.axesSpec || umi.spec.axesSpec.length < 2) return null;

  return [
    { inputName: "x", selectedSource: umi.spec.axesSpec[1] },
    { inputName: "y", selectedSource: umi.spec.axesSpec[0] },
    { inputName: "valueSize", selectedSource: umi.spec },
    { inputName: "valueColor", selectedSource: fraction.spec },
  ];
});
</script>

<template>
  <GraphMaker
    v-model="app.model.data.bindingBubbleState"
    chart-type="bubble"
    :p-frame="app.model.outputs.bindingPf"
    :default-options="defaultOptions"
  />
</template>
