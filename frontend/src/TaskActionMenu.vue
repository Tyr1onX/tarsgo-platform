<script setup lang="ts">
import ActionMenu from "./components/ActionMenu.vue"

export interface TaskActionMenuItem {
  key: string
  label: string
  disabled?: boolean
  danger?: boolean
}

withDefaults(defineProps<{
  taskId: number | string
  actions: TaskActionMenuItem[]
  disabled?: boolean
  ariaLabel?: string
}>(), {
  ariaLabel: "任务更多操作",
})

const emit = defineEmits<{ select: [key: string] }>()
</script>

<template>
  <ActionMenu
    :id="`task-${taskId}`"
    :actions="actions"
    :disabled="disabled"
    :aria-label="ariaLabel"
    @select="emit('select', $event)"
  />
</template>
