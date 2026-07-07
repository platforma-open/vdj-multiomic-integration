<script setup lang="ts">
import {
  PlAgDataTableV2,
  PlAlert,
  PlBlockPage,
  PlBtnGhost,
  PlDropdown,
  PlDropdownRef,
  PlNumberField,
  PlSlideModal,
  usePlDataTableSettingsV2,
} from "@platforma-sdk/ui-vue";
import { ref } from "vue";
import { useApp } from "../app";

const app = useApp();
// Auto-open Settings when the block is first added and its required inputs are
// unset (mirrors feature-integration). Local ref initialised from data — never
// a watcher writing back to data (would be a hairpin).
const settingsOpen = ref(
  app.model.data.datasetRef === undefined || app.model.data.featureColumnId === undefined,
);

const tableSettings = usePlDataTableSettingsV2({
  model: () => app.model.outputs.clonotypeTable,
});
</script>

<template>
  <PlBlockPage>
    <template #title>VDJ Multiomic Integration</template>
    <template #append>
      <PlBtnGhost @click.stop="settingsOpen = true">Settings</PlBtnGhost>
    </template>

    <PlAgDataTableV2
      v-if="app.model.outputs.clonotypeTable"
      v-model="app.model.data.tableState"
      :settings="tableSettings"
      show-export-button
    />
    <PlAlert v-else type="info">
      Select the VDJ single-cell dataset and Feature Integration column via Settings, then run the
      block to see per-clonotype results.
    </PlAlert>

    <PlSlideModal v-model="settingsOpen">
      <template #title>Settings</template>
      <PlDropdownRef
        v-model="app.model.data.datasetRef"
        :options="app.model.outputs.datasetOptions"
        label="VDJ single-cell dataset"
        required
      />
      <PlDropdown
        v-model="app.model.data.featureColumnId"
        :options="app.model.outputs.featureOptions"
        label="Feature Integration per-cell column"
        required
      />
      <PlDropdown
        v-model="app.model.data.annotationColumnId"
        :options="app.model.outputs.annotationOptions"
        label="Cell-type annotation (optional)"
      />
      <PlNumberField
        v-model="app.model.data.dominanceThreshold"
        label="Dominance threshold"
        :min-value="0.5"
        :max-value="1.0"
        :step="0.05"
      />
      <PlNumberField
        v-model="app.model.data.presenceThreshold"
        label="Presence threshold (breadth)"
        :min-value="0.0"
        :max-value="1.0"
        :step="0.05"
      />
    </PlSlideModal>
  </PlBlockPage>
</template>
