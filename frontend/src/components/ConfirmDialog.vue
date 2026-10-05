<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, useId, watch } from "vue"

const props = withDefaults(
  defineProps<{
    open: boolean
    title: string
    description: string
    confirmLabel?: string
    cancelLabel?: string
    danger?: boolean
    pending?: boolean
    disabled?: boolean
  }>(),
  {
    confirmLabel: "确认",
    cancelLabel: "取消",
    danger: false,
    pending: false,
    disabled: false,
  },
)

const emit = defineEmits<{
  confirm: []
  cancel: []
}>()

const dialog = ref<HTMLElement | null>(null)
const cancelButton = ref<HTMLButtonElement | null>(null)
const returnFocus = ref<HTMLElement | null>(null)
const uid = useId()
const titleId = `${uid}-title`
const descriptionId = `${uid}-description`

function requestClose() {
  if (props.pending) return
  emit("cancel")
}

function requestConfirm() {
  if (props.pending || props.disabled) return
  emit("confirm")
}

function focusableButtons() {
  return [...(dialog.value?.querySelectorAll<HTMLButtonElement>("button:not(:disabled)") ?? [])]
}

function onKeydown(event: KeyboardEvent) {
  if (!props.open) return

  if (event.key === "Escape") {
    if (props.pending) return
    event.preventDefault()
    requestClose()
    return
  }

  if (event.key !== "Tab") return
  const buttons = focusableButtons()
  if (!buttons.length) {
    event.preventDefault()
    dialog.value?.focus()
    return
  }

  const first = buttons[0]
  const last = buttons[buttons.length - 1]
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last?.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first?.focus()
  }
}

watch(
  () => props.open,
  async (open, wasOpen) => {
    if (open) {
      await nextTick()
      returnFocus.value = document.activeElement instanceof HTMLElement ? document.activeElement : null
      document.addEventListener("keydown", onKeydown)
      cancelButton.value?.focus()
      return
    }

    if (!wasOpen) return
    document.removeEventListener("keydown", onKeydown)
    const target = returnFocus.value
    returnFocus.value = null
    await nextTick()
    if (target?.isConnected) target.focus()
  },
  { flush: "post" },
)

onBeforeUnmount(() => {
  document.removeEventListener("keydown", onKeydown)
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="confirm-dialog-backdrop"
      @click.self="requestClose"
    >
      <section
        ref="dialog"
        class="confirm-dialog"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="titleId"
        :aria-describedby="descriptionId"
        :aria-busy="pending"
        tabindex="-1"
      >
        <h2 :id="titleId">{{ title }}</h2>
        <p :id="descriptionId">{{ description }}</p>
        <div class="confirm-dialog-actions">
          <button
            ref="cancelButton"
            class="confirm-dialog-cancel"
            type="button"
            :disabled="pending"
            @click="requestClose"
          >
            {{ cancelLabel }}
          </button>
          <button
            class="confirm-dialog-confirm"
            :class="{ danger }"
            type="button"
            :disabled="pending || disabled"
            @click="requestConfirm"
          >
            {{ pending ? "处理中…" : confirmLabel }}
          </button>
        </div>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.confirm-dialog-backdrop {
  position: fixed;
  z-index: 1200;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 12px;
  background: rgba(27, 26, 24, 0.18);
}

.confirm-dialog {
  width: min(100%, 420px);
  max-height: calc(100dvh - 24px);
  overflow: auto;
  border: 1px solid var(--line-strong);
  border-radius: 6px;
  background: var(--surface);
  padding: 18px;
  box-shadow: 0 6px 20px rgba(27, 26, 24, 0.12);
}

.confirm-dialog h2 {
  margin: 0 0 7px;
  font-size: 18px;
  line-height: 1.35;
}

.confirm-dialog p {
  margin: 0;
  color: var(--secondary);
  font-size: 13.5px;
  line-height: 1.6;
  overflow-wrap: anywhere;
}

.confirm-dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 18px;
}

.confirm-dialog-actions button {
  min-height: 36px;
  border: 1px solid var(--line-strong);
  border-radius: 4px;
  padding: 7px 12px;
}

.confirm-dialog-cancel {
  background: transparent;
  color: var(--secondary);
}

.confirm-dialog-cancel:hover:not(:disabled) {
  background: var(--hover);
  color: var(--text);
}

.confirm-dialog-confirm {
  background: var(--primary-bg);
  color: var(--primary-fg);
}

.confirm-dialog-confirm:hover:not(:disabled) {
  background: var(--primary-hover-bg);
}

.confirm-dialog-confirm.danger {
  border-color: var(--line-strong);
  background: transparent;
  color: var(--danger);
}

.confirm-dialog-confirm.danger:hover:not(:disabled) {
  background: var(--hover);
}

.confirm-dialog-actions button:disabled {
  cursor: wait;
  opacity: 0.68;
}

@media (max-width: 400px) {
  .confirm-dialog-backdrop {
    padding: 10px;
  }

  .confirm-dialog {
    width: 100%;
    max-width: calc(100vw - 20px);
    padding: 16px;
  }

  .confirm-dialog-actions {
    flex-wrap: wrap;
  }
}
</style>
