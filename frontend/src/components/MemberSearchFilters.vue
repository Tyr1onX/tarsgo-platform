<script setup lang="ts">
import type { TeamGroup } from "../types"

const props = defineProps<{
  query: string
  group: string
  groupLabels: Record<TeamGroup, string>
  searchLabel: string
  searchPlaceholder: string
}>()

const emit = defineEmits<{
  "update:query": [value: string]
  "update:group": [value: string]
}>()

const groupOptions = Object.entries(props.groupLabels).map(([value, label]) => ({
  value,
  label,
}))
</script>

<template>
  <div class="member-search-filters">
    <label>
      {{ searchLabel }}
      <input
        type="search"
        :value="query"
        :placeholder="searchPlaceholder"
        @input="emit('update:query', ($event.target as HTMLInputElement).value)"
      />
    </label>
    <label>
      所属组别
      <select :value="group" @change="emit('update:group', ($event.target as HTMLSelectElement).value)">
        <option value="">全部组别</option>
        <option v-for="option in groupOptions" :key="option.value" :value="option.value">
          {{ option.label }}
        </option>
        <option value="unassigned">组别未填写</option>
      </select>
    </label>
  </div>
</template>

<style scoped>
.member-search-filters {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(140px, 210px);
  align-items: end;
  gap: 9px;
  width: 100%;
  min-width: 0;
  margin: 10px 0 12px;
}

.member-search-filters label {
  display: grid;
  gap: 5px;
  min-width: 0;
  color: var(--muted);
  font-size: 12px;
}

.member-search-filters input,
.member-search-filters select {
  min-width: 0;
  margin: 0;
  padding: 9px 10px;
  font-size: 14px;
}

@media (max-width: 560px) {
  .member-search-filters {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
