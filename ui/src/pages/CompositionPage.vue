<script setup lang="ts">
import type { PredefinedGraphOption } from "@milaboratories/graph-maker";
import { GraphMaker } from "@milaboratories/graph-maker";
import { computed } from "vue";
import { useApp } from "../app";

const app = useApp();

// Per-annotation composition: one barplot panel per annotation (facet), with that annotation's dominant
// categories on the x-axis and clonotype count on y. Reads the small pre-aggregated composition frame — a
// single count column keyed [annotation, category] — so it's flat in dataset size. Categories sit on the
// x-axis (not a color stack), so each panel shows only its own categories and there is no shared legend.
const defaultOptions = computed((): PredefinedGraphOption<"discrete">[] | null => {
  const pCols = app.model.outputs.compositionPCols;
  if (!pCols || pCols.length === 0) return null;

  const count = pCols.find((p) => p.spec.name === "pl7.app/vdj/clonotypeCount");
  if (!count || !count.spec.axesSpec || count.spec.axesSpec.length < 2) return null;

  return [
    { inputName: "y", selectedSource: count.spec },
    { inputName: "primaryGrouping", selectedSource: count.spec.axesSpec[1] }, // category (x within a panel)
    { inputName: "facetBy", selectedSource: count.spec.axesSpec[0] }, // annotation (one panel each)
  ];
});
</script>

<template>
  <GraphMaker
    v-model="app.model.data.compositionState"
    chart-type="discrete"
    :p-frame="app.model.outputs.compositionPf"
    :default-options="defaultOptions"
  />
</template>
