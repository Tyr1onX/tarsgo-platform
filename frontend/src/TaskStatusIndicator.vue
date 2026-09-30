<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from "vue"
import type { TaskStatus } from "./types"

const props = withDefaults(defineProps<{
  status: TaskStatus
  taskId: number | string
  editable?: boolean
  pending?: boolean
  blocked?: boolean
}>(), {
  editable: false,
  pending: false,
  blocked: false,
})

const emit = defineEmits<{ "update-status": [status: TaskStatus] }>()

const labels: Record<TaskStatus, string> = {
  todo: "待开始",
  doing: "进行中",
  done: "已完成",
}
const options: TaskStatus[] = ["todo", "doing", "done"]
const menuOpen = ref(false)
const alignRight = ref(false)
const root = ref<HTMLElement | null>(null)
const trigger = ref<HTMLButtonElement | null>(null)
const optionButtons = ref<HTMLButtonElement[]>([])
const menuId = `task-status-menu-${props.taskId}`

function closeMenu(returnFocus = false) {
  menuOpen.value = false
  alignRight.value = false
  if (returnFocus) void nextTick(() => trigger.value?.focus())
}

function toggleMenu() {
  if (props.pending) return
  menuOpen.value = !menuOpen.value
  if (menuOpen.value) {
    void nextTick(() => {
      const triggerBounds = trigger.value?.getBoundingClientRect()
      const menuBounds = root.value?.querySelector<HTMLElement>(".task-status-menu")?.getBoundingClientRect()
      alignRight.value = Boolean(triggerBounds && menuBounds && menuBounds.right > window.innerWidth - 8)
      const selectedIndex = options.indexOf(props.status)
      optionButtons.value[selectedIndex]?.focus()
    })
  }
}

function chooseStatus(status: TaskStatus) {
  if (status !== props.status) emit("update-status", status)
  closeMenu(true)
}

function onPointerDown(event: PointerEvent) {
  if (menuOpen.value && event.target instanceof Node && !root.value?.contains(event.target)) closeMenu()
}

function onDocumentKeydown(event: KeyboardEvent) {
  if (menuOpen.value && event.key === "Escape") {
    event.preventDefault()
    closeMenu(true)
  }
}

function onMenuKeydown(event: KeyboardEvent) {
  if (event.key === "Tab") {
    closeMenu()
    return
  }
  const currentIndex = optionButtons.value.indexOf(document.activeElement as HTMLButtonElement)
  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    event.preventDefault()
    const direction = event.key === "ArrowDown" ? 1 : -1
    const nextIndex = (currentIndex + direction + options.length) % options.length
    optionButtons.value[nextIndex]?.focus()
  } else if (event.key === "Home" || event.key === "End") {
    event.preventDefault()
    optionButtons.value[event.key === "Home" ? 0 : options.length - 1]?.focus()
  }
}

onMounted(() => {
  document.addEventListener("pointerdown", onPointerDown)
  document.addEventListener("keydown", onDocumentKeydown)
})

onBeforeUnmount(() => {
  document.removeEventListener("pointerdown", onPointerDown)
  document.removeEventListener("keydown", onDocumentKeydown)
})
</script>

<template>
  <div v-if="editable" ref="root" class="task-status-wrap" :class="{ 'is-open': menuOpen }">
    <button
      ref="trigger"
      class="task-status-indicator is-editable"
      :class="`status-${status}`"
      type="button"
      aria-haspopup="menu"
      :aria-expanded="menuOpen"
      :aria-controls="menuId"
      :aria-busy="pending"
      :disabled="pending"
      @click="toggleMenu"
    >
      <svg class="task-status-icon" viewBox="0 0 20 20" aria-hidden="true">
        <circle cx="10" cy="10" r="7.1" />
        <path v-if="status === 'doing'" class="status-progress-half" d="M10 2.9a7.1 7.1 0 0 1 0 14.2z" />
        <path v-else-if="status === 'done'" class="status-check" d="m6.2 10.2 2.4 2.4 5.3-5.4" />
      </svg>
      <span>{{ labels[status] }}</span>
      <span v-if="blocked" class="task-status-blocked">等待前置</span>
      <span v-if="pending" class="task-status-pending">更新中…</span>
      <svg class="task-status-caret" viewBox="0 0 12 12" aria-hidden="true"><path d="m3 4.5 3 3 3-3" /></svg>
    </button>
    <div v-if="menuOpen" :id="menuId" class="task-status-menu" :class="{ 'align-right': alignRight }" role="menu" :aria-label="`更改任务状态，当前${labels[status]}`" @keydown="onMenuKeydown">
      <button
        v-for="(option, index) in options"
        :key="option"
        :ref="(element) => { if (element) optionButtons[index] = element as HTMLButtonElement }"
        class="task-status-menu-option"
        :class="{ selected: status === option, [`status-${option}`]: true }"
        type="button"
        role="menuitemradio"
        :aria-checked="status === option"
        @click="chooseStatus(option)"
      >
        <svg class="task-status-icon" viewBox="0 0 20 20" aria-hidden="true">
          <circle cx="10" cy="10" r="7.1" />
          <path v-if="option === 'doing'" class="status-progress-half" d="M10 2.9a7.1 7.1 0 0 1 0 14.2z" />
          <path v-else-if="option === 'done'" class="status-check" d="m6.2 10.2 2.4 2.4 5.3-5.4" />
        </svg>
        <span>{{ labels[option] }}</span>
        <svg v-if="status === option" class="task-status-selected" viewBox="0 0 16 16" aria-hidden="true"><path d="m3.5 8.2 2.8 2.7 6.2-6.1" /></svg>
      </button>
    </div>
  </div>
  <span
    v-else
    class="task-status-indicator"
    :class="`status-${status}`"
    :aria-label="`${labels[status]}${blocked ? '，等待前置任务' : ''}`"
  >
    <svg class="task-status-icon" viewBox="0 0 20 20" aria-hidden="true">
      <circle cx="10" cy="10" r="7.1" />
      <path v-if="status === 'doing'" class="status-progress-half" d="M10 2.9a7.1 7.1 0 0 1 0 14.2z" />
      <path v-else-if="status === 'done'" class="status-check" d="m6.2 10.2 2.4 2.4 5.3-5.4" />
    </svg>
    <span>{{ labels[status] }}</span>
    <span v-if="blocked" class="task-status-blocked">等待前置</span>
  </span>
</template>
