<script setup lang="ts">
import { computed, ref, watch } from "vue"

import { validateFileSelection } from "../fileDropzone.js"

const props = withDefaults(defineProps<{
  accept?: string
  maxSize?: number
  disabled?: boolean
  uploading?: boolean
  label?: string
  hint?: string
}>(), {
  accept: "",
  maxSize: 0,
  disabled: false,
  uploading: false,
  label: "将文件拖到这里，或点击选择文件",
  hint: "",
})

const emit = defineEmits<{
  "file-selected": [file: File]
}>()

const fileInput = ref<HTMLInputElement | null>(null)
const dragDepth = ref(0)
const dragging = ref(false)
const selectedFileName = ref("")
const validationError = ref("")

const inactive = computed(() => props.disabled || props.uploading)

function resetDragState() {
  dragDepth.value = 0
  dragging.value = false
}

watch(inactive, (value) => {
  if (value) resetDragState()
})

function isFileDrag(event: DragEvent) {
  return Array.from(event.dataTransfer?.types ?? []).includes("Files")
}

function openPicker() {
  if (inactive.value) return
  fileInput.value?.click()
}

function selectFile(file: File | undefined) {
  if (!file || inactive.value) return

  const nextError = validateFileSelection(file, {
    accept: props.accept,
    maxSize: props.maxSize,
  })
  validationError.value = nextError
  if (nextError) return

  selectedFileName.value = file.name
  emit("file-selected", file)
}

function onInputChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ""
  selectFile(file)
}

function onDragEnter(event: DragEvent) {
  if (inactive.value || !isFileDrag(event)) return
  dragDepth.value += 1
  dragging.value = true
}

function onDragOver(event: DragEvent) {
  if (inactive.value || !isFileDrag(event)) return
  if (event.dataTransfer) event.dataTransfer.dropEffect = "copy"
}

function onDragLeave(event: DragEvent) {
  if (inactive.value || !isFileDrag(event)) return
  dragDepth.value = Math.max(0, dragDepth.value - 1)
  if (dragDepth.value === 0) dragging.value = false
}

function onDrop(event: DragEvent) {
  const file = event.dataTransfer?.files?.[0]
  resetDragState()
  selectFile(file)
}
</script>

<template>
  <div
    class="file-dropzone"
    :class="{ 'is-dragging': dragging, 'is-disabled': inactive }"
    role="button"
    :tabindex="inactive ? -1 : 0"
    :aria-disabled="inactive"
    :aria-busy="uploading || undefined"
    @click="openPicker"
    @keydown.enter.prevent="openPicker"
    @keydown.space.prevent="openPicker"
    @dragenter.prevent="onDragEnter"
    @dragover.prevent="onDragOver"
    @dragleave.prevent="onDragLeave"
    @drop.prevent="onDrop"
  >
    <input
      ref="fileInput"
      class="file-dropzone-input"
      type="file"
      :accept="accept"
      :disabled="inactive"
      tabindex="-1"
      @click.stop
      @change="onInputChange"
    />

    <strong v-if="uploading && selectedFileName">{{ selectedFileName }}</strong>
    <template v-else>
      <strong class="file-dropzone-label-desktop">{{ dragging ? "松开即可上传" : label }}</strong>
      <strong class="file-dropzone-label-mobile">{{ dragging ? "松开即可上传" : "点击选择文件" }}</strong>
    </template>
    <small v-if="uploading && selectedFileName">上传中…</small>
    <small v-else-if="hint">{{ hint }}</small>
    <small v-if="validationError" class="file-dropzone-error">{{ validationError }}</small>
  </div>
</template>

<style scoped>
.file-dropzone {
  width: 100%;
  min-width: 0;
  min-height: 64px;
  display: grid;
  align-content: center;
  gap: 3px;
  box-sizing: border-box;
  padding: 10px 12px;
  border: 1px dashed var(--line-strong);
  background: var(--surface);
  color: var(--secondary);
  cursor: pointer;
  overflow-wrap: anywhere;
  transition: border-color 120ms ease, background-color 120ms ease;
}

.file-dropzone:hover,
.file-dropzone:focus-visible,
.file-dropzone.is-dragging {
  border-color: var(--text);
  background: var(--hover);
  outline: none;
}

.file-dropzone.is-disabled {
  cursor: default;
  opacity: 0.58;
}

.file-dropzone.is-disabled:hover {
  border-color: var(--line-strong);
  background: var(--surface);
}

.file-dropzone strong {
  color: var(--text);
  font-size: 13px;
  font-weight: 560;
}

.file-dropzone small {
  color: var(--muted);
  font-size: 12px;
  line-height: 1.45;
}

.file-dropzone-error {
  color: var(--danger) !important;
}

.file-dropzone-input {
  display: none;
}

.file-dropzone-label-mobile {
  display: none;
}

@media (max-width: 520px) {
  .file-dropzone {
    min-height: 52px;
    padding: 9px 10px;
  }

  .file-dropzone-label-desktop {
    display: none;
  }

  .file-dropzone-label-mobile {
    display: block;
  }
}
</style>