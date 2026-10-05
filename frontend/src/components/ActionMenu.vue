<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from "vue"

export interface ActionMenuItem {
  key: string
  label: string
  disabled?: boolean
  danger?: boolean
}

const props = withDefaults(
  defineProps<{
    id: number | string
    actions: ActionMenuItem[]
    disabled?: boolean
    ariaLabel?: string
  }>(),
  {
    disabled: false,
    ariaLabel: "更多操作",
  },
)

const emit = defineEmits<{ select: [key: string] }>()
const open = ref(false)
const alignRight = ref(false)
const openAbove = ref(false)
const root = ref<HTMLElement | null>(null)
const trigger = ref<HTMLButtonElement | null>(null)
const menu = ref<HTMLElement | null>(null)
const actionButtons = ref<HTMLButtonElement[]>([])
const menuId = `action-menu-${String(props.id).replace(/[^a-zA-Z0-9_-]/g, "-")}`

function enabledButtons() {
  return actionButtons.value.filter((button) => !button.disabled)
}

function close(returnFocus = false) {
  open.value = false
  alignRight.value = false
  openAbove.value = false
  actionButtons.value = []
  if (returnFocus) void nextTick(() => trigger.value?.focus())
}

function toggle() {
  if (props.disabled || !props.actions.length) return
  open.value = !open.value
  if (!open.value) return

  void nextTick(() => {
    const anchor = root.value?.getBoundingClientRect()
    const bounds = menu.value?.getBoundingClientRect()
    if (anchor && bounds) {
      alignRight.value = anchor.left + bounds.width > window.innerWidth - 8
      openAbove.value = anchor.bottom + bounds.height > window.innerHeight - 8
    }
    enabledButtons()[0]?.focus()
  })
}

function selectAction(action: ActionMenuItem) {
  if (props.disabled || action.disabled) return
  close(true)
  emit("select", action.key)
}

function onPointerDown(event: PointerEvent) {
  if (open.value && event.target instanceof Node && !root.value?.contains(event.target)) close()
}

function onDocumentKeydown(event: KeyboardEvent) {
  if (open.value && event.key === "Escape") {
    event.preventDefault()
    close(true)
  }
}

function onMenuKeydown(event: KeyboardEvent) {
  if (event.key === "Tab") {
    close()
    return
  }

  const buttons = enabledButtons()
  if (!buttons.length) return
  const currentIndex = buttons.indexOf(document.activeElement as HTMLButtonElement)

  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    event.preventDefault()
    const direction = event.key === "ArrowDown" ? 1 : -1
    const startIndex = currentIndex < 0 ? (direction > 0 ? -1 : 0) : currentIndex
    const nextIndex = (startIndex + direction + buttons.length) % buttons.length
    buttons[nextIndex]?.focus()
  } else if (event.key === "Home" || event.key === "End") {
    event.preventDefault()
    buttons[event.key === "Home" ? 0 : buttons.length - 1]?.focus()
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
  <div v-if="actions.length" ref="root" class="action-menu-wrap">
    <button
      ref="trigger"
      class="action-menu-trigger"
      type="button"
      :aria-label="ariaLabel"
      aria-haspopup="menu"
      :aria-expanded="open"
      :aria-controls="menuId"
      :disabled="disabled"
      @click="toggle"
    >
      <svg viewBox="0 0 16 16" aria-hidden="true">
        <circle cx="3" cy="8" r="1" />
        <circle cx="8" cy="8" r="1" />
        <circle cx="13" cy="8" r="1" />
      </svg>
    </button>
    <div
      v-if="open"
      :id="menuId"
      ref="menu"
      class="action-menu"
      :class="{ 'align-right': alignRight, 'open-above': openAbove }"
      role="menu"
      :aria-label="ariaLabel"
      @keydown="onMenuKeydown"
    >
      <button
        v-for="(action, index) in actions"
        :key="action.key"
        :ref="(element) => { if (element) actionButtons[index] = element as HTMLButtonElement }"
        class="action-menu-item"
        :class="{ danger: action.danger }"
        type="button"
        role="menuitem"
        :disabled="disabled || action.disabled"
        @click="selectAction(action)"
      >{{ action.label }}</button>
    </div>
  </div>
</template>
