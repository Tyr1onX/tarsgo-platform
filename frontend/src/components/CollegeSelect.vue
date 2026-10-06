<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, useId, watch } from "vue"

import type { CollegeOption } from "../types"
import { collegeMenuPlacement, filterCollegeOptions, moveCollegeActiveIndex } from "../collegeSelect.js"

const props = withDefaults(defineProps<{
  modelValue: string
  options: CollegeOption[]
  clearable?: boolean
  required?: boolean
  invalid?: boolean
  placeholder?: string
}>(), {
  clearable: false,
  required: false,
  invalid: false,
  placeholder: "搜索学院",
})

const emit = defineEmits<{
  "update:modelValue": [value: string]
  change: []
}>()

const listboxId = `college-select-options-${useId()}`
const rootRef = ref<HTMLDivElement | null>(null)
const inputRef = ref<HTMLInputElement | null>(null)
const query = ref("")
const isOpen = ref(false)
const opensAbove = ref(false)
const menuMaxHeight = ref(280)
const activeIndex = ref(-1)
let skipNextModelSync = false

const filteredOptions = computed(() => filterCollegeOptions(props.options, query.value))
const activeOptionId = computed(() =>
  activeIndex.value >= 0 ? `${listboxId}-option-${activeIndex.value}` : undefined,
)

function syncQueryFromModel() {
  if (isOpen.value) return
  query.value = props.options.find((option) => option.code === props.modelValue)?.name ?? ""
}

watch(() => props.modelValue, () => {
  if (skipNextModelSync) {
    skipNextModelSync = false
    return
  }
  syncQueryFromModel()
}, { immediate: true })
watch(() => props.options, syncQueryFromModel)
watch(activeIndex, (index) => {
  if (index < 0) return
  requestAnimationFrame(() => {
    document.getElementById(`${listboxId}-option-${index}`)?.scrollIntoView({ block: "nearest" })
  })
})

function updatePlacement() {
  const bounds = rootRef.value?.getBoundingClientRect()
  if (!bounds) return
  const viewport = window.visualViewport
  const viewportTop = viewport?.offsetTop ?? 0
  const viewportHeight = viewport?.height ?? window.innerHeight
  const placement = collegeMenuPlacement(
    viewportHeight,
    bounds.top - viewportTop,
    bounds.bottom - viewportTop,
  )
  opensAbove.value = placement.opensAbove
  menuMaxHeight.value = placement.maxHeight
}

function openMenu() {
  updatePlacement()
  isOpen.value = true
}

function closeMenu() {
  isOpen.value = false
  activeIndex.value = -1
}

function onInput(event: Event) {
  query.value = (event.target as HTMLInputElement).value
  openMenu()
  activeIndex.value = filteredOptions.value.length ? 0 : -1
  if (props.modelValue) {
    skipNextModelSync = true
    emit("update:modelValue", "")
  }
  emit("change")
}

function chooseCollege(option: CollegeOption) {
  query.value = option.name
  closeMenu()
  if (props.modelValue !== option.code) {
    skipNextModelSync = true
    emit("update:modelValue", option.code)
  }
  emit("change")
  inputRef.value?.focus()
}

function clearSelection() {
  query.value = ""
  closeMenu()
  if (props.modelValue) {
    skipNextModelSync = true
    emit("update:modelValue", "")
    emit("change")
  }
  inputRef.value?.focus()
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    event.preventDefault()
    openMenu()
    activeIndex.value = moveCollegeActiveIndex(
      activeIndex.value,
      event.key === "ArrowDown" ? "down" : "up",
      filteredOptions.value.length,
    )
    return
  }

  if (event.key === "Enter" && isOpen.value) {
    event.preventDefault()
    if (activeIndex.value >= 0) {
      const option = filteredOptions.value[activeIndex.value]
      if (option) chooseCollege(option)
    }
    return
  }

  if (event.key === "Escape" && isOpen.value) {
    event.preventDefault()
    closeMenu()
  }
}

function onOutsidePointer(event: PointerEvent) {
  if (!rootRef.value?.contains(event.target as Node)) closeMenu()
}

function onFocusOut(event: FocusEvent) {
  if (!rootRef.value?.contains(event.relatedTarget as Node | null)) closeMenu()
}

function onViewportResize() {
  if (isOpen.value) updatePlacement()
}

onMounted(() => {
  document.addEventListener("pointerdown", onOutsidePointer)
  window.addEventListener("resize", onViewportResize)
  window.visualViewport?.addEventListener("resize", onViewportResize)
})

onBeforeUnmount(() => {
  document.removeEventListener("pointerdown", onOutsidePointer)
  window.removeEventListener("resize", onViewportResize)
  window.visualViewport?.removeEventListener("resize", onViewportResize)
})
</script>

<template>
  <div ref="rootRef" class="college-select" @focusout="onFocusOut">
    <input
      ref="inputRef"
      class="college-select__input"
      type="text"
      role="combobox"
      :value="query"
      :placeholder="placeholder"
      :required="required"
      :aria-required="required || undefined"
      :aria-invalid="invalid || undefined"
      aria-autocomplete="list"
      aria-haspopup="listbox"
      :aria-expanded="isOpen"
      :aria-controls="listboxId"
      :aria-activedescendant="activeOptionId"
      autocomplete="off"
      @focus="openMenu"
      @click="openMenu"
      @input="onInput"
      @keydown="onKeydown"
    />
    <button
      v-if="clearable && modelValue"
      class="college-select__clear"
      type="button"
      aria-label="清空学院"
      @mousedown.prevent
      @click="clearSelection"
    >
      ×
    </button>

    <div
      v-show="isOpen"
      class="college-select__menu"
      :class="{ 'college-select__menu--above': opensAbove }"
      :style="{ maxHeight: `${menuMaxHeight}px` }"
    >
      <ul :id="listboxId" role="listbox" aria-label="学院选项">
        <li
          v-for="(college, index) in filteredOptions"
          :id="`${listboxId}-option-${index}`"
          :key="college.code"
          role="option"
          :aria-selected="modelValue === college.code"
          :class="{ 'is-active': activeIndex === index }"
          @mouseenter="activeIndex = index"
          @mousedown.prevent
          @click="chooseCollege(college)"
        >
          {{ college.name }}
        </li>
      </ul>
      <p v-if="!filteredOptions.length" class="college-select__empty" role="status">
        没有匹配的学院
      </p>
    </div>
  </div>
</template>

<style scoped>
.college-select {
  position: relative;
  width: 100%;
  min-width: 0;
}

.college-select__input {
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
}

.college-select__clear {
  position: absolute;
  top: 50%;
  right: 9px;
  width: 26px;
  height: 26px;
  transform: translateY(-50%);
  border: 0;
  border-radius: 3px;
  background: transparent;
  color: var(--muted);
  font-size: 18px;
  line-height: 1;
}

.college-select__menu {
  position: absolute;
  z-index: 80;
  top: calc(100% + 4px);
  left: 0;
  width: 100%;
  max-width: calc(100vw - 24px);
  max-height: min(280px, calc(100vh - 24px));
  max-height: min(280px, calc(100dvh - 24px));
  overflow-y: auto;
  overscroll-behavior: contain;
  border: 1px solid var(--line-strong);
  border-radius: 4px;
  background: var(--surface);
}

.college-select__menu--above {
  top: auto;
  bottom: calc(100% + 4px);
}

.college-select__menu ul {
  display: grid;
  gap: 2px;
  margin: 0;
  padding: 4px;
  list-style: none;
}

.college-select__menu li {
  min-width: 0;
  border-radius: 3px;
  padding: 7px 9px;
  color: var(--text);
  cursor: pointer;
  overflow-wrap: anywhere;
}

.college-select__menu li:hover,
.college-select__menu li.is-active {
  background: var(--hover);
}

.college-select__empty {
  margin: 0;
  padding: 9px;
  color: var(--muted);
  font-size: 13px;
}
</style>
