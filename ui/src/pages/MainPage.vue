<script setup lang="ts">
import {
  createPlDataTableStateV2,
  type IntegrationEntry,
  type PlRef,
} from "@platforma-open/milaboratories.vdj-multiomic-integration.model";
import {
  PlAgDataTableV2,
  PlAlert,
  PlBlockPage,
  PlBtnGhost,
  PlBtnSecondary,
  PlDropdown,
  PlDropdownMulti,
  PlDropdownRef,
  PlElementList,
  PlMaskIcon24,
  PlNumberField,
  PlSlideModal,
  usePlDataTableSettingsV2,
} from "@platforma-sdk/ui-vue";
import { computed, ref, watch } from "vue";
import { useApp } from "../app";

const app = useApp();

// Auto-open Settings when the block is first added and the dataset is unset. Local ref initialised from
// data — never a watcher writing back to data (would be a hairpin).
const settingsOpen = ref(app.model.data.datasetRef === undefined);

// Close Settings once the run starts, so the results take over the page.
watch(
  () => app.model.outputs.isRunning,
  (isRunning) => {
    if (isRunning) settingsOpen.value = false;
  },
);

// The dataset is the anchor only (clonotype space + cell linker). Per-cell inputs are chosen explicitly
// as integration cards below, so picking the dataset writes only the ref (and resets the grid state).
function setDataset(dsRef?: PlRef) {
  app.model.data.datasetRef = dsRef;
  if (dsRef === undefined) return;
  app.model.data.tableState = createPlDataTableStateV2();
}

// The integration cards, bound so PlElementList can reorder/remove via immutable writes.
const integrationItems = computed<IntegrationEntry[]>({
  get: () => app.model.data.integrations ?? [],
  set: (v) => {
    app.model.data.integrations = v;
  },
});

// A card's data selector options: every discovered per-cell column, minus the ones already chosen in
// OTHER cards (each column integrated at most once). The card's own current pick stays available.
function optionsForCard(cardId: string) {
  const chosenElsewhere = new Set(
    integrationItems.value.filter((i) => i.id !== cardId && i.ref).map((i) => i.ref),
  );
  return (app.model.outputs.integrationOptions ?? [])
    .filter((o) => !chosenElsewhere.has(o.value))
    .map((o) => ({ label: `${o.label} (${o.kind})`, value: o.value }));
}

let idCounter = 0;
const expandedIntegrations = ref(new Set<string>());

// "Add data" appends an empty card and opens it, so the user picks the data inside it (Lead Selection
// pattern). An empty card gates the run until it gets a selection or is removed (enforced in the model).
function addCard() {
  idCounter += 1;
  const id = `int-${idCounter}-${Date.now()}`;
  app.model.data.integrations = [...integrationItems.value, { id }];
  expandedIntegrations.value = new Set(expandedIntegrations.value).add(id);
}

// Snapshot the chosen option's ref / kind / label into the card (snapshot-on-gesture; keeps args pure).
function selectData(id: string, value: string | undefined) {
  const opt = value
    ? (app.model.outputs.integrationOptions ?? []).find((o) => o.value === value)
    : undefined;
  patchIntegration(id, { ref: opt?.value, kind: opt?.kind, label: opt?.label });
}

// Immutable per-card update (new references, no in-place mutation) — monorepo Vue-reactivity rule.
function patchIntegration(id: string, patch: Partial<IntegrationEntry>) {
  app.model.data.integrations = integrationItems.value.map((i) =>
    i.id === id ? { ...i, ...patch } : i,
  );
}

// Off-target designation (F2). The property dropdown lists Feature Integration's imported per-feature
// properties (from the model's spec-derived options); the value multi-select lists the chosen property's
// distinct values. Changing the property clears the selected values (they belong to the old property).
const offtargetPropertyDropdownOptions = computed(() =>
  (app.model.outputs.offtargetPropertyOptions ?? []).map((o) => ({
    value: o.propertyName,
    label: o.label,
  })),
);
function offtargetValueOptions(propertyName?: string) {
  const opts = app.model.outputs.offtargetPropertyOptions ?? [];
  const p = opts.find((o) => o.propertyName === propertyName);
  return (p?.values ?? []).map((v) => ({ value: v, label: v }));
}
function setOfftargetProperty(id: string, propertyName: string | undefined) {
  patchIntegration(id, { offtargetProperty: propertyName, offtargetValues: undefined });
}

function toggleIntegration(id: string) {
  const next = new Set(expandedIntegrations.value);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  expandedIntegrations.value = next;
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
    <template #title>Clonotype Multiomic Integration</template>
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
      Select the VDJ single-cell dataset, add at least one integration, then run the block to see
      per-clonotype results.
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
          The clonotype space and the cell linker come from this dataset. Add the per-cell data to
          integrate below.
        </template>
      </PlDropdownRef>

      <PlElementList
        v-model:items="integrationItems"
        :get-item-key="(item) => item.id"
        :disable-dragging="true"
        :disable-pinning="true"
        :is-expanded="(item) => expandedIntegrations.has(item.id)"
        :on-expand="(item) => toggleIntegration(item.id)"
      >
        <template #item-title="{ item }">{{ item.label || "Select data" }}</template>
        <template #item-content="{ item }">
          <PlDropdown
            :model-value="item.ref"
            :options="optionsForCard(item.id)"
            label="Data"
            @update:model-value="(v) => selectData(item.id, v)"
          >
            <template #tooltip>
              Choose single-cell data to bring onto your clonotypes: antigen binding, or a cell
              annotation such as cell type.
            </template>
          </PlDropdown>

          <template v-if="item.kind">
            <PlNumberField
              v-if="item.kind === 'feature'"
              :model-value="item.presenceThreshold ?? 0"
              :min-value="0"
              :max-value="1"
              :step="0.05"
              label="Presence threshold"
              @update:model-value="(v) => patchIntegration(item.id, { presenceThreshold: v })"
            >
              <template #tooltip>
                Minimum within-clonotype fraction for a feature to count as bound, applied to every
                feature. Feeds breadth and the dominant call. 0 = any signal counts; raise it to
                require stronger, more consistent binding across the clonotype's cells before a
                feature is counted.
              </template>
            </PlNumberField>
            <PlNumberField
              :model-value="item.dominanceThreshold ?? 0.6"
              :min-value="0.5"
              :max-value="1.0"
              :step="0.05"
              label="Dominance threshold"
              @update:model-value="(v) => patchIntegration(item.id, { dominanceThreshold: v })"
            >
              <template #tooltip>
                Minimum share the top {{ item.kind === "feature" ? "feature" : "category" }} must
                reach to be this clonotype's dominant call; below that, the call is "ambiguous".
                Raise it for stricter, cleaner calls; lower it toward the 0.5 floor to still call
                clonotypes with more mixed signal.
              </template>
            </PlNumberField>
            <!-- Type-aware off-target call + "cross-reactive" label (F2 designation). MILAB-6496. -->
            <PlDropdown
              v-if="item.kind === 'feature'"
              :model-value="item.offtargetProperty"
              :options="offtargetPropertyDropdownOptions"
              label="Off-target property"
              clearable
              @update:model-value="(v) => setOfftargetProperty(item.id, v)"
            >
              <template #tooltip>
                Optional. Pick an imported per-feature property (e.g. antigen type) that marks
                features as on- or off-target, then choose the off-target values below. Off-target
                features drop out of the dominant call, and cross-reactive on-target binders get a
                "cross-reactive" label instead of "ambiguous".
              </template>
            </PlDropdown>
            <PlDropdownMulti
              v-if="item.kind === 'feature' && item.offtargetProperty"
              :model-value="item.offtargetValues ?? []"
              :options="offtargetValueOptions(item.offtargetProperty)"
              label="Off-target values"
              @update:model-value="(v) => patchIntegration(item.id, { offtargetValues: v })"
            >
              <template #tooltip>
                Property values that mark a feature as off-target (e.g. "Off-Target", "Decoy").
              </template>
            </PlDropdownMulti>
          </template>
        </template>
      </PlElementList>

      <PlBtnSecondary icon="add" @click="addCard">Add data</PlBtnSecondary>
    </PlSlideModal>
  </PlBlockPage>
</template>
