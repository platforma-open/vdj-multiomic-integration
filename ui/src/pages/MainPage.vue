<script setup lang="ts">
import {
  type AntigenSetting,
  createPlDataTableStateV2,
  type PlRef,
} from "@platforma-open/milaboratories.vdj-multiomic-integration.model";
import {
  PlAgDataTableV2,
  PlAlert,
  PlBlockPage,
  PlBtnGhost,
  PlDropdown,
  PlDropdownRef,
  PlElementList,
  PlMaskIcon24,
  PlNumberField,
  PlSlideModal,
  usePlDataTableSettingsV2,
} from "@platforma-sdk/ui-vue";
import { computed, ref } from "vue";
import { useApp } from "../app";
import AntigenCard from "./AntigenCard.vue";

const app = useApp();

// Auto-open Settings when the block is first added and the dataset is unset. Local ref initialised from
// data — never a watcher writing back to data (would be a hairpin). featureColumnId is auto-selected on
// dataset pick, so the dataset is the only required manual choice.
const settingsOpen = ref(app.model.data.datasetRef === undefined);

const expressionMethodOptions = [
  { label: "Mean", value: "mean" as const },
  { label: "Max", value: "max" as const },
];

// Dataset pick auto-discovers the per-cell inputs that share the sample + cell-barcode join key: the
// block selects the feature/antigen column (required) plus GEX and cell-type annotation (optional) from
// the pool-wide discovery outputs. A setter on the user's gesture, NOT a watcher on an output — it reads
// the current option outputs and writes data once (the sanctioned snapshot-on-gesture pattern).
function setDataset(dsRef?: PlRef) {
  app.model.data.datasetRef = dsRef;
  if (dsRef === undefined) return;
  app.model.data.featureColumnId = app.model.outputs.featureOptions?.[0]?.value;
  app.model.data.gexColumnId = app.model.outputs.gexOptions?.[0]?.value;
  app.model.data.annotationColumnId = app.model.outputs.annotationOptions?.[0]?.value;
  app.model.data.tableState = createPlDataTableStateV2();
}

// Antigens discovered from the last run -> one card each. A derived (read-only) items list; PlElementList
// never mutates it because dragging/removing/pinning are disabled, so a plain computed is safe as :items.
const antigenItems = computed(() =>
  (app.model.outputs.antigenOptions ?? []).map((name) => ({ name })),
);

// Card expansion is view-local (a Set of expanded antigen names), kept out of persisted data.
const expanded = ref(new Set<string>());
function toggleExpanded(name: string) {
  const next = new Set(expanded.value);
  if (next.has(name)) next.delete(name);
  else next.add(name);
  expanded.value = next;
}

// Guarded read: a block created before this field existed has no antigenSettings (undefined).
const antigenSettings = computed<Record<string, AntigenSetting>>(
  () => app.model.data.antigenSettings ?? {},
);

// Immutable per-antigen update (new references, no in-place mutation) — monorepo Vue-reactivity rule.
function patchAntigen(name: string, patch: Partial<AntigenSetting>) {
  const settings = antigenSettings.value;
  const current = settings[name] ?? {};
  app.model.data.antigenSettings = { ...settings, [name]: { ...current, ...patch } };
}
function isHidden(name: string) {
  return antigenSettings.value[name]?.hidden === true;
}
function presenceThresholdOf(name: string) {
  return antigenSettings.value[name]?.presenceThreshold;
}

const tableSettings = usePlDataTableSettingsV2({
  model: () => app.model.outputs.clonotypeTable,
});
</script>

<template>
  <PlBlockPage
    v-model:subtitle="app.model.data.customBlockLabel"
    :subtitle-placeholder="app.model.data.defaultBlockLabel"
  >
    <template #title>VDJ Multiomic Integration</template>
    <template #append>
      <PlBtnGhost @click.stop="settingsOpen = true">
        Settings
        <template #append>
          <PlMaskIcon24 name="settings" />
        </template>
      </PlBtnGhost>
    </template>

    <PlAgDataTableV2
      v-if="app.model.outputs.clonotypeTable"
      v-model="app.model.data.tableState"
      :settings="tableSettings"
      show-export-button
    />
    <PlAlert v-else type="info">
      Select the VDJ single-cell dataset via Settings, then run the block to see per-clonotype
      results.
    </PlAlert>

    <PlSlideModal v-model="settingsOpen">
      <template #title>Settings</template>
      <PlDropdownRef
        :model-value="app.model.data.datasetRef"
        :options="app.model.outputs.datasetOptions"
        label="VDJ single-cell dataset"
        required
        @update:model-value="setDataset"
      >
        <template #tooltip>
          The feature/antigen, gene-expression and cell-type inputs are auto-discovered from this
          dataset via the shared sample + cell barcode.
        </template>
      </PlDropdownRef>

      <PlDropdown
        v-if="app.model.data.gexColumnId"
        v-model="app.model.data.expressionMethod"
        :options="expressionMethodOptions"
        label="Expression aggregation"
      />

      <PlNumberField
        v-model="app.model.data.dominanceThreshold"
        label="Dominance threshold"
        :min-value="0.5"
        :max-value="1.0"
        :step="0.05"
      >
        <template #tooltip>
          Minimum share the top antigen (or cell type) must reach to be called the clonotype's
          dominant one; below it the clonotype is "ambiguous". Floor 0.5.
        </template>
      </PlNumberField>

      <template v-if="antigenItems.length > 0">
        <PlElementList
          :items="antigenItems"
          :get-item-key="(item) => item.name"
          :disable-dragging="true"
          :disable-removing="true"
          :disable-pinning="true"
          :is-expanded="(item) => expanded.has(item.name)"
          :on-expand="(item) => toggleExpanded(item.name)"
          :is-toggled="(item) => isHidden(item.name)"
          :on-toggle="(item) => patchAntigen(item.name, { hidden: !isHidden(item.name) })"
        >
          <template #item-title="{ item }">{{ item.name }}</template>
          <template #item-content="{ item }">
            <AntigenCard
              :name="item.name"
              :threshold="presenceThresholdOf(item.name)"
              @update:threshold="(v) => patchAntigen(item.name, { presenceThreshold: v })"
            />
          </template>
        </PlElementList>
      </template>
    </PlSlideModal>
  </PlBlockPage>
</template>
