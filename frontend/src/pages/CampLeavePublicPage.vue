<script setup lang="ts">
import { onMounted, ref } from "vue"

import { ApiError, api } from "../api"
import type { CampLeavePublicEvent, CollegeOption } from "../types"

const props = defineProps<{ token: string }>()
const event = ref<CampLeavePublicEvent | null>(null)
const colleges = ref<CollegeOption[]>([])
const loading = ref(true)
const saving = ref(false)
const submitted = ref(false)
const error = ref("")
const fieldErrors = ref<Record<string, string>>({})
const draft = ref({ name: "", student_id: "", college: "" })

function typeLabel(type: "winter" | "summer") {
  return type === "winter" ? "冬令营" : "夏令营"
}

function dateSpan(start: string, end: string) {
  return start === end ? start : `${start} 至 ${end}`
}

function dateTime(value: string) {
  return value.slice(0, 16).replace("T", " ")
}

function setFieldError(field: string, message: string) {
  fieldErrors.value = { ...fieldErrors.value, [field]: message }
}

function clearFieldError(field: string) {
  const next = { ...fieldErrors.value }
  delete next[field]
  fieldErrors.value = next
}

async function load() {
  loading.value = true
  try {
    const [eventInfo, options] = await Promise.all([
      api.publicCampLeaveEvent(props.token),
      api.colleges(),
    ])
    event.value = eventInfo
    colleges.value = options
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "报名链接无效或已失效。"
  } finally {
    loading.value = false
  }
}

async function submit() {
  error.value = ""
  fieldErrors.value = {}
  const name = draft.value.name.trim()
  const studentId = draft.value.student_id.trim()
  if (name.length < 2 || name.length > 50) setFieldError("name", "姓名长度需为 2–50 个字符")
  if (!/^[0-9]{8}$/.test(studentId)) setFieldError("student_id", "学号必须是 8 位数字")
  if (!draft.value.college) setFieldError("college", "请选择所属学院")
  if (Object.keys(fieldErrors.value).length) return

  saving.value = true
  try {
    await api.publicJoinCampLeaveEvent(props.token, {
      name,
      student_id: studentId,
      college: draft.value.college,
    })
    submitted.value = true
  } catch (reason) {
    if (reason instanceof ApiError && reason.field) setFieldError(reason.field, reason.message)
    else error.value = reason instanceof Error ? reason.message : "报名失败，请稍后重试。"
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <section class="camp-public-form">
    <p class="brand">TARS BASE</p>
    <template v-if="loading">
      <h1>集中请假报名</h1>
      <p class="camp-public-muted" role="status">正在读取活动信息…</p>
    </template>
    <template v-else-if="event && submitted">
      <span class="camp-public-kicker">{{ typeLabel(event.type) }}</span>
      <h1>报名已提交</h1>
      <p class="camp-public-muted">已记录你的信息。请关闭此页面，名单仅供活动管理员查看。</p>
    </template>
    <template v-else-if="event">
      <span class="camp-public-kicker">{{ typeLabel(event.type) }}</span>
      <h1>{{ event.title }}</h1>
      <p class="camp-public-muted">活动时间：{{ dateSpan(event.start_date, event.end_date) }}</p>
      <p class="camp-public-muted">收集截止：{{ dateTime(event.collection_deadline) }}</p>
      <template v-if="event.accepting_participants">
        <p class="camp-public-hint">请填写姓名、学号和所属学院。此入口仅用于本次活动报名。</p>
        <p v-if="error" class="camp-public-error" role="alert">{{ error }}</p>
        <form @submit.prevent="submit">
          <label>
            姓名
            <input v-model="draft.name" autocomplete="name" maxlength="50" required :aria-invalid="Boolean(fieldErrors.name)" @input="clearFieldError('name')" />
            <small v-if="fieldErrors.name" class="camp-public-error">{{ fieldErrors.name }}</small>
          </label>
          <label>
            学号
            <input v-model="draft.student_id" inputmode="numeric" autocomplete="off" maxlength="8" required :aria-invalid="Boolean(fieldErrors.student_id)" @input="clearFieldError('student_id')" />
            <small v-if="fieldErrors.student_id" class="camp-public-error">{{ fieldErrors.student_id }}</small>
          </label>
          <label>
            所属学院
            <select v-model="draft.college" required :aria-invalid="Boolean(fieldErrors.college)" @change="clearFieldError('college')">
              <option value="" disabled>请选择学院</option>
              <option v-for="college in colleges" :key="college.code" :value="college.code">{{ college.name }}</option>
            </select>
            <small v-if="fieldErrors.college" class="camp-public-error">{{ fieldErrors.college }}</small>
          </label>
          <button class="primary" type="submit" :disabled="saving">{{ saving ? "正在提交…" : "提交报名" }}</button>
        </form>
      </template>
      <p v-else class="camp-public-muted">本次活动已停止收集报名。</p>
    </template>
    <template v-else>
      <span class="camp-public-kicker">BASE / CAMP LEAVE</span>
      <h1>无法打开报名</h1>
      <p class="camp-public-error" role="alert">{{ error || "报名链接无效或已失效。" }}</p>
    </template>
  </section>
</template>

<style scoped>
.camp-public-form { box-sizing: border-box; width: 100%; min-width: 0; }
.camp-public-form .brand { margin: 0 0 24px; color: var(--text); font-weight: 650; letter-spacing: .08em; }
.camp-public-kicker { color: var(--faint); font-size: 12px; }
.camp-public-form h1 { margin-top: 5px; overflow-wrap: anywhere; }
.camp-public-muted, .camp-public-hint { color: var(--muted); font-size: 13px; line-height: 1.55; overflow-wrap: anywhere; }
.camp-public-error { color: var(--danger); font-size: 12px; }
.camp-public-form form { display: grid; gap: 15px; margin-top: 20px; }
.camp-public-form label { min-width: 0; }
.camp-public-form input, .camp-public-form select { box-sizing: border-box; width: 100%; min-width: 0; }
.camp-public-form small { display: block; margin-top: 4px; }
</style>
