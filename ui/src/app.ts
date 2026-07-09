import { platforma } from "@platforma-open/milaboratories.vdj-multiomic-integration.model";
import { defineAppV3 } from "@platforma-sdk/ui-vue";
import { watchEffect } from "vue";
import CompositionPage from "./pages/CompositionPage.vue";
import DistributionPage from "./pages/DistributionPage.vue";
import HeatmapPage from "./pages/HeatmapPage.vue";
import MainPage from "./pages/MainPage.vue";

export const sdkPlugin = defineAppV3(platforma, (app) => {
  app.model.data.customBlockLabel ??= "";

  // Keep the default block label in sync with the selected dataset's label, so the subtitle and the
  // downstream trace prefix reflect this instance's input. This output -> data write is intentional and
  // narrow: it only writes the derived default, never the user's customBlockLabel.
  watchEffect(() => {
    const datasetRef = app.model.data.datasetRef;
    const options = app.model.outputs.datasetOptions ?? [];
    const match = datasetRef
      ? options.find(
          (o) => o.ref?.blockId === datasetRef.blockId && o.ref?.name === datasetRef.name,
        )
      : undefined;
    app.model.data.defaultBlockLabel = match?.label ?? "";
  });

  return {
    // Drive the block spinner while the long-running aggregation is executing.
    progress: () => app.model.outputs.isRunning,
    routes: {
      "/": () => MainPage,
      "/heatmap": () => HeatmapPage,
      "/distribution": () => DistributionPage,
      "/composition": () => CompositionPage,
    },
  };
});

export const useApp = sdkPlugin.useApp;
