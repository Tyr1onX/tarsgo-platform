<script setup lang="ts">
import ActionMenu from "./components/ActionMenu.vue"

export interface TaskActionMenuItem {
  key: string
  label: string
  disabled?: boolean
  danger?: boolean
}

defineProps<{
  taskId: number | string
  actions: TaskActionMenuItem[]
  disabled?: boolean
}>()

const emit = defineEmits<{ select: [key: string] }>()
</script>

<template>
  <ActionMenu
    :id="`task-${taskId}`"
    :actions="actions"
    :disabled="disabled"
    aria-label="任务更多操作"
    @select="emit('select', $event)"
  />
</template>
