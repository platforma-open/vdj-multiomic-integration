import { platforma } from "@platforma-open/milaboratories.vdj-multiomic-integration.model";
import { defineAppV3 } from "@platforma-sdk/ui-vue";
import DistributionPage from "./pages/DistributionPage.vue";
import HeatmapPage from "./pages/HeatmapPage.vue";
import MainPage from "./pages/MainPage.vue";

export const sdkPlugin = defineAppV3(platforma, (app) => {
  return {
    // Drive the block spinner while the long-running aggregation is executing.
    progress: () => app.model.outputs.isRunning,
    routes: {
      "/": () => MainPage,
      "/heatmap": () => HeatmapPage,
      "/distribution": () => DistributionPage,
    },
  };
});

export const useApp = sdkPlugin.useApp;
