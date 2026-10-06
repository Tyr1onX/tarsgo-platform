<script setup lang="ts">
import { onMounted, ref } from "vue"

import { api } from "../api"
import type { Member, SchoolLeaveRequest, SchoolLeaveRun } from "../types"

const props = defineProps<{ currentUser: Member }>()
const requests = ref<SchoolLeaveRequest[]>([])
const runs = ref<SchoolLeaveRun[]>([])
const loading = ref(true)
const error = ref("")
const downloading = ref<number | null>(null)

const isAdmin = props.currentUser.role === "admin"

function dateTime(value: string) {
  return value.slice(0, 16).replace("T", " ")
}

function statusLabel(run: SchoolLeaveRun) {
  if (run.status === "completed") return "已完成"
  if (run.status === "awaiting_return") return "回传处理中"
  if (run.status === "ready") return "待下载"
  return "已取消"
}

async function load() {
  loading.value = true
  error.value = ""
  try {
    if (isAdmin) runs.value = await api.schoolLeaveRuns()
    else requests.value = await api.schoolLeaveRequests()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "历史记录加载失败"
  } finally {
    loading.value = false
  }
}

function openResult(runId: number, groupIndex: number) {
  window.open(api.schoolLeaveResultUrl(runId, groupIndex), "_blank", "noopener")
}

async function downloadRun(run: SchoolLeaveRun) {
  downloading.value = run.id
  error.value = ""
  try {
    const file = await api.downloadLegacySchoolLeaveRunDocument(run.id)
    const url = URL.createObjectURL(file.blob)
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = file.filename
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    URL.revokeObjectURL(url)
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "下载失败"
  } finally {
    downloading.value = null
  }
}

async function downloadGroup(runId: number, groupIndex: number) {
  downloading.value = runId
  error.value = ""
  try {
    const file = await api.downloadLegacySchoolLeaveGroupDocument(runId, groupIndex)
    const url = URL.createObjectURL(file.blob)
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = file.filename
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    URL.revokeObjectURL(url)
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "下载失败"
  } finally {
    downloading.value = null
  }
}

onMounted(load)
</script>

<template>
  <section class="legacy-leave-history" aria-label="旧版日常请假历史">
    <p v-if="error" class="legacy-leave-error" role="alert">{{ error }}</p>
    <p v-if="loading" class="legacy-leave-muted" role="status">正在加载历史记录…</p>
    <template v-else-if="isAdmin">
      <p v-if="!runs.length" class="legacy-leave-muted">暂无旧版历史记录。</p>
      <article v-for="run in runs" :key="run.id" class="legacy-leave-run">
        <div class="legacy-leave-run-heading">
          <strong>{{ dateTime(run.collected_at) }} · {{ statusLabel(run) }}</strong>
          <button
            v-if="run.document_ready && run.status !== 'cancelled'"
            class="text-action"
            type="button"
            :disabled="downloading === run.id"
            @click="downloadRun(run)"
          >{{ downloading === run.id ? "准备中…" : "下载原汇总 DOCX" }}</button>
        </div>
        <p class="legacy-leave-muted">{{ run.request_count }} 条历史申请 · {{ run.groups.length }} 个时间组</p>
        <div v-for="group in run.groups" :key="group.index" class="legacy-leave-group">
          <div class="legacy-leave-group-heading">
            <span>{{ dateTime(group.start_at) }} 至 {{ dateTime(group.end_at) }} · {{ group.count }} 人</span>
            <button
              v-if="run.status !== 'cancelled'"
              class="text-action"
              type="button"
              :disabled="downloading === run.id"
              @click="downloadGroup(run.id, group.index)"
            >下载此组 DOCX</button>
          </div>
          <div v-for="person in group.members" :key="person.member_id" class="legacy-leave-person">
            <span>{{ person.name }} · {{ person.student_id }}</span>
            <button
              v-if="group.result?.available"
              class="text-action"
              type="button"
              @click="openResult(run.id, group.index)"
            >下载历史回传材料</button>
          </div>
        </div>
      </article>
    </template>
    <template v-else>
      <p v-if="!requests.length" class="legacy-leave-muted">暂无旧版历史记录。</p>
      <div v-for="item in requests" :key="item.id" class="legacy-leave-member-row">
        <span>{{ dateTime(item.start_at) }} 至 {{ dateTime(item.end_at) }} · {{ item.status === "withdrawn" ? "已撤回" : item.run_status === "completed" ? "已完成" : "已汇总" }}</span>
        <button
          v-if="item.run_id !== null && item.group_index !== null && item.result_state === 'available'"
          class="text-action"
          type="button"
          @click="openResult(item.run_id, item.group_index)"
        >下载历史回传材料</button>
      </div>
    </template>
  </section>
</template>

<style scoped>
.legacy-leave-history { min-width: 0; }
.legacy-leave-muted { margin: 7px 0; color: var(--faint); font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }
.legacy-leave-error { margin: 7px 0; color: var(--danger); font-size: 12px; }
.legacy-leave-run { min-width: 0; padding: 11px 0; border-top: 1px solid var(--line); }
.legacy-leave-run-heading, .legacy-leave-group-heading, .legacy-leave-member-row, .legacy-leave-person { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; min-width: 0; }
.legacy-leave-run-heading strong { font-size: 13px; font-weight: 560; }
.legacy-leave-run-heading button, .legacy-leave-group-heading button, .legacy-leave-person button, .legacy-leave-member-row button { flex: 0 0 auto; padding: 2px 0; }
.legacy-leave-group { padding: 7px 0 0; }
.legacy-leave-group-heading, .legacy-leave-person, .legacy-leave-member-row { padding: 6px 0; border-top: 1px solid var(--line); font-size: 12px; overflow-wrap: anywhere; }
.legacy-leave-person span, .legacy-leave-member-row span { min-width: 0; overflow-wrap: anywhere; }
@media (max-width: 420px) { .legacy-leave-run-heading, .legacy-leave-group-heading, .legacy-leave-member-row, .legacy-leave-person { align-items: flex-start; } }
</style>
