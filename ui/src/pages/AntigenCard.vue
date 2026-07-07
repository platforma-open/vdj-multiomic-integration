<script setup lang="ts">
import { PlNumberField } from "@platforma-sdk/ui-vue";

// One antigen's Settings card body. The eye/hide toggle is owned by the PlElementList item header in
// MainPage; this card carries the per-antigen presence threshold. Explicit prop + emit (no defineModel
// on an object) per the monorepo Vue-reactivity rules.
defineProps<{ name: string; threshold: number | undefined }>();
const emit = defineEmits<{ (e: "update:threshold", value: number | undefined): void }>();
</script>

<template>
  <PlNumberField
    :model-value="threshold ?? 0"
    :min-value="0"
    :max-value="1"
    :step="0.05"
    label="Presence threshold"
    @update:model-value="(v: number | undefined) => emit('update:threshold', v)"
  >
    <template #tooltip>
      Minimum within-clonotype fraction for {{ name }} to count as bound in this clonotype. Raises
      the bar for {{ name }} in breadth and the dominant-antigen call. 0 = any signal counts.
    </template>
  </PlNumberField>
</template>
