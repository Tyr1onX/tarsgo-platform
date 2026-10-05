<script setup lang="ts">
import { computed, onMounted, ref } from "vue"

import { api } from "../api"
import type {
  Member,
  SchoolLeaveAdminConfig,
  SchoolLeaveAdminSummary,
  SchoolLeaveRequest,
  SchoolLeaveRun,
} from "../types"

const props = defineProps<{ currentUser: Member }>()
const emit = defineEmits<{
  navigate: [path: string]
  todoCount: [count: number]
}>()

const requests = ref<SchoolLeaveRequest[]>([])
const adminRequests = ref<SchoolLeaveRequest[]>([])
const runs = ref<SchoolLeaveRun[]>([])
const config = ref<SchoolLeaveAdminConfig | null>(null)
const summary = ref<SchoolLeaveAdminSummary | null>(null)
const loading = ref(true)
const saving = ref(false)
const actionRunId = ref<number | null>(null)
const error = ref("")
const notice = ref("")
const editingRequestId = ref<number | null>(null)
const reasonDrafts = ref<Record<number, string>>({})
const previewKey = ref("")
const pendingPreviewKey = ref("")
const editingReasonRunId = ref<number | null>(null)
const historyExpanded = ref(false)
const activeView = ref<"mine" | "admin">("mine")

function shanghaiToday() {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date())
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]))
  return `${values.year}-${values.month}-${values.day}`
}

const leaveDate = ref(shanghaiToday())
const startTime = ref("13:00")
const endTime = ref("17:00")

const isAdmin = computed(() => props.currentUser.role === "admin")
const pendingAdminRequests = computed(() => adminRequests.value.filter((item) => item.status === "pending"))
const pendingMemberCount = computed(() => new Set(pendingAdminRequests.value.map((item) => item.member_id)).size)
const readyRuns = computed(() => runs.value.filter((item) => item.status === "ready"))
const awaitingReturnRuns = computed(() => runs.value.filter((item) => item.status === "awaiting_return"))
const completedRuns = computed(() => runs.value.filter((item) => item.status === "completed"))
const visibleCompletedRuns = computed(() =>
  historyExpanded.value ? completedRuns.value : completedRuns.value.slice(0, 3),
)
const pendingPreviewDays = computed(() => {
  const days = new Map<string, Map<string, {
    key: string
    startAt: string
    endAt: string
    requests: SchoolLeaveRequest[]
  }>>()

  for (const request of pendingAdminRequests.value) {
    const date = request.start_at.slice(0, 10)
    const exactKey = request.start_at + "\u0000" + request.end_at
    let groups = days.get(date)
    if (!groups) {
      groups = new Map()
      days.set(date, groups)
    }
    let group = groups.get(exactKey)
    if (!group) {
      group = { key: exactKey, startAt: request.start_at, endAt: request.end_at, requests: [] }
      groups.set(exactKey, group)
    }
    group.requests.push(request)
  }

  return [...days.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([date, groups]) => ({
      date,
      groups: [...groups.values()].sort(
        (left, right) => left.startAt.localeCompare(right.startAt) || left.endAt.localeCompare(right.endAt),
      ),
    }))
})

function messageOf(reason: unknown) {
  return reason instanceof Error ? reason.message : "操作失败"
}

function toInputParts(value: string) {
  const [datePart, timePart = ""] = value.split("T")
  return { date: datePart, time: timePart.slice(0, 5) }
}

function formatMonthDay(date: string) {
  const [, month = "", day = ""] = date.split("-")
  return Number(month) + " 月 " + Number(day) + " 日"
}

function formatDateTime(value: string | null) {
  if (!value) return ""
  const parts = toInputParts(value)
  return formatMonthDay(parts.date) + " · " + parts.time
}

function formatCollectedAt(value: string) {
  const parts = toInputParts(value)
  const day = parts.date === shanghaiToday() ? "今天" : formatMonthDay(parts.date)
  return day + " " + parts.time + " 汇总"
}

function formatRange(item: Pick<SchoolLeaveRequest, "start_at" | "end_at">) {
  const start = toInputParts(item.start_at)
  const end = toInputParts(item.end_at)
  if (start.date === end.date) return formatMonthDay(start.date) + " · " + start.time + "–" + end.time
  return formatMonthDay(start.date) + " " + start.time + " → " + formatMonthDay(end.date) + " " + end.time
}

function formatTimeSpan(startAt: string, endAt: string) {
  const start = toInputParts(startAt)
  const end = toInputParts(endAt)
  if (start.date === end.date) return start.time + "–" + end.time
  return formatMonthDay(start.date) + " " + start.time + " → " + formatMonthDay(end.date) + " " + end.time
}

function requestStatusLabel(item: SchoolLeaveRequest) {
  if (item.status === "pending") return "待汇总"
  if (item.status === "withdrawn") return "已撤回"
  if (item.run_status === "awaiting_return") return "办理中"
  if (item.run_status === "completed" && item.result_state === "cleared") return "已完成 · 材料已清理"
  if (item.run_status === "completed") return "已完成"
  return "已汇总"
}

function localDateTime(date: string, time: string) {
  return `${date}T${time}:00`
}

async function load() {
  loading.value = true
  error.value = ""
  try {
    requests.value = await api.schoolLeaveRequests()
    if (isAdmin.value) {
      const [nextConfig, nextSummary, nextAdminRequests, nextRuns] = await Promise.all([
        api.schoolLeaveAdminConfig(),
        api.schoolLeaveAdminSummary(),
        api.schoolLeaveAdminRequests(),
        api.schoolLeaveRuns(),
      ])
      config.value = nextConfig
      summary.value = nextSummary
      adminRequests.value = nextAdminRequests
      runs.value = nextRuns
      reasonDrafts.value = Object.fromEntries(nextRuns.map((run) => [run.id, run.reason]))
      emit("todoCount", nextSummary.todo_count)
    }
  } catch (reason) {
    error.value = messageOf(reason)
  } finally {
    loading.value = false
  }
}

function resetForm() {
  editingRequestId.value = null
  leaveDate.value = shanghaiToday()
  startTime.value = "13:00"
  endTime.value = "17:00"
}

async function submitRequest() {
  error.value = ""
  notice.value = ""
  if (!props.currentUser.student_id) {
    error.value = "请先完善学号，生成学校请假材料时需要使用。"
    return
  }
  if (!leaveDate.value || !startTime.value || !endTime.value) {
    error.value = "请填写明确的请假日期和时间。"
    return
  }
  saving.value = true
  try {
    const startAt = localDateTime(leaveDate.value, startTime.value)
    const endAt = localDateTime(leaveDate.value, endTime.value)
    if (editingRequestId.value === null) {
      await api.createSchoolLeaveRequest(startAt, endAt)
      notice.value = "请假申请已提交。"
    } else {
      await api.updateSchoolLeaveRequest(editingRequestId.value, startAt, endAt)
      notice.value = "请假时间已更新。"
    }
    resetForm()
    await load()
  } catch (reason) {
    error.value = messageOf(reason)
  } finally {
    saving.value = false
  }
}

function editRequest(item: SchoolLeaveRequest) {
  const start = toInputParts(item.start_at)
  const end = toInputParts(item.end_at)
  if (start.date !== end.date) {
    error.value = "该申请为跨日时间，请撤回后按实际时间重新提交。"
    return
  }
  editingRequestId.value = item.id
  leaveDate.value = start.date
  startTime.value = start.time
  endTime.value = end.time
  window.scrollTo({ top: 0, behavior: "smooth" })
}

async function withdrawRequest(item: SchoolLeaveRequest) {
  if (!window.confirm("撤回这条待汇总请假申请？")) return
  error.value = ""
  notice.value = ""
  try {
    await api.withdrawSchoolLeaveRequest(item.id)
    if (editingRequestId.value === item.id) resetForm()
    notice.value = "请假申请已撤回。"
    await load()
  } catch (reason) {
    error.value = messageOf(reason)
  }
}

async function collectNow() {
  actionRunId.value = 0
  error.value = ""
  notice.value = ""
  try {
    const result = await api.collectSchoolLeave()
    notice.value = result ? "已生成新的请假汇总批次。" : "当前没有待汇总申请。"
    await load()
  } catch (reason) {
    error.value = messageOf(reason)
  } finally {
    actionRunId.value = null
  }
}

function startReasonEdit(run: SchoolLeaveRun, event?: Event) {
  closeOverflow(event)
  reasonDrafts.value[run.id] = run.reason
  editingReasonRunId.value = run.id
}

function cancelReasonEdit(run: SchoolLeaveRun) {
  reasonDrafts.value[run.id] = run.reason
  editingReasonRunId.value = null
}

async function saveReason(run: SchoolLeaveRun) {
  actionRunId.value = run.id
  error.value = ""
  notice.value = ""
  try {
    await api.updateSchoolLeaveRunReason(run.id, reasonDrafts.value[run.id] ?? "")
    editingReasonRunId.value = null
    notice.value = "统一请假事由已更新。"
    await load()
  } catch (reason) {
    error.value = messageOf(reason)
  } finally {
    actionRunId.value = null
  }
}

async function cancelRun(run: SchoolLeaveRun, event?: Event) {
  closeOverflow(event)
  if (!window.confirm("取消本次汇总？其中申请会退回待汇总并可由成员重新修改。")) return
  actionRunId.value = run.id
  error.value = ""
  notice.value = ""
  try {
    await api.cancelSchoolLeaveRun(run.id)
    notice.value = "本次汇总已取消，申请已退回待汇总。"
    await load()
  } catch (reason) {
    error.value = messageOf(reason)
  } finally {
    actionRunId.value = null
  }
}

async function deleteRun(run: SchoolLeaveRun, event?: Event) {
  closeOverflow(event)
  const confirmed = window.confirm(
    "删除这条已完成记录？\n\n" +
    "将同时删除该批次下的 " + run.request_count + " 条请假申请和盖章材料。\n" +
    "此操作不可恢复。",
  )
  if (!confirmed) return
  actionRunId.value = run.id
  error.value = ""
  notice.value = ""
  try {
    await api.deleteSchoolLeaveRun(run.id)
    runs.value = runs.value.filter((item) => item.id !== run.id)
    notice.value = "历史记录已删除。"
    await load()
  } catch (reason) {
    error.value = messageOf(reason)
  } finally {
    actionRunId.value = null
  }
}

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

async function downloadRunDocument(run: SchoolLeaveRun) {
  actionRunId.value = run.id
  error.value = ""
  try {
    const file = await api.downloadSchoolLeaveRunDocument(run.id)
    saveBlob(file.blob, file.filename)
    await load()
  } catch (reason) {
    error.value = messageOf(reason)
  } finally {
    actionRunId.value = null
  }
}

async function uploadResult(run: SchoolLeaveRun, groupIndex: number, event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ""
  if (!file) return
  actionRunId.value = run.id
  error.value = ""
  notice.value = ""
  try {
    await api.uploadSchoolLeaveResult(run.id, groupIndex, file)
    notice.value = "盖章结果已上传。"
    await load()
  } catch (reason) {
    error.value = messageOf(reason)
  } finally {
    actionRunId.value = null
  }
}

function resultUrl(runId: number, groupIndex: number) {
  return api.schoolLeaveResultUrl(runId, groupIndex)
}

function openResult(runId: number, groupIndex: number) {
  window.open(resultUrl(runId, groupIndex), "_blank", "noopener")
}

function togglePreview(runId: number, groupIndex: number) {
  const key = `${runId}:${groupIndex}`
  previewKey.value = previewKey.value === key ? "" : key
}

function togglePendingPreview(key: string) {
  pendingPreviewKey.value = pendingPreviewKey.value === key ? "" : key
}

function closeOverflow(event?: Event) {
  const details = (event?.currentTarget as HTMLElement | null)?.closest("details")
  details?.removeAttribute("open")
}

function dayKey(value: string) {
  return value.slice(0, 10)
}

function isSupplementRun(run: SchoolLeaveRun) {
  return runs.value.some(
    (other) =>
      other.id < run.id &&
      other.status !== "cancelled" &&
      dayKey(other.collected_at) === dayKey(run.collected_at),
  )
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="page-title leave-page-title"><h1>学校请假</h1></div>

  <nav v-if="isAdmin" class="leave-view-tabs" aria-label="学校请假视图">
    <button type="button" :class="{ active: activeView === 'mine' }" @click="activeView = 'mine'">我的请假</button>
    <button type="button" :class="{ active: activeView === 'admin' }" @click="activeView = 'admin'">汇总管理</button>
  </nav>

  <p v-if="error" class="leave-feedback leave-error">{{ error }}</p>
  <p v-if="notice" class="leave-feedback leave-success">{{ notice }}</p>

  <template v-if="activeView === 'mine' || !isAdmin">
    <section v-if="!currentUser.student_id" class="leave-inline-notice">
      <span>请先完善学号，生成学校请假材料时需要使用。</span>
      <button type="button" @click="emit('navigate', '/me')">去完善</button>
    </section>

    <section class="leave-submit-section">
      <div class="section-heading">
        <h2>{{ editingRequestId === null ? "提交请假" : "修改请假" }}</h2>
        <button v-if="editingRequestId !== null" type="button" @click="resetForm">取消修改</button>
      </div>
      <form class="leave-request-form" @submit.prevent="submitRequest">
        <div class="leave-form-controls">
          <label>
            <span>请假日期</span>
            <input v-model="leaveDate" type="date" required />
          </label>
          <div class="leave-time-pair">
            <label><span>开始时间</span><input v-model="startTime" type="time" step="300" required /></label>
            <span class="leave-time-arrow" aria-hidden="true">→</span>
            <label><span>结束时间</span><input v-model="endTime" type="time" step="300" required /></label>
          </div>
          <button class="primary leave-submit" type="submit" :disabled="saving || !currentUser.student_id">
            {{ saving ? "正在保存…" : editingRequestId === null ? "提交请假" : "保存修改" }}
          </button>
        </div>
        <p class="leave-help">相同请假时间会自动汇总到同一份请假材料中，请按自己的实际缺课时间填写。</p>
      </form>
    </section>

    <section class="leave-my-requests">
      <div class="section-heading"><h2>我的申请</h2></div>
      <div v-if="loading" class="leave-empty">正在加载…</div>
      <div v-else-if="requests.length === 0" class="leave-empty">暂无请假申请</div>
      <div v-else class="leave-list">
        <div
          v-for="item in requests"
          :key="item.id"
          class="leave-row"
          :class="{ 'leave-row-muted': item.status === 'withdrawn' }"
        >
          <div class="leave-row-main">
            <strong>{{ formatRange(item) }}</strong>
            <span>{{ requestStatusLabel(item) }}</span>
          </div>
          <div v-if="item.status === 'pending'" class="row-actions leave-row-actions">
            <button type="button" @click="editRequest(item)">修改</button>
            <button class="danger-text" type="button" @click="withdrawRequest(item)">撤回</button>
          </div>
          <button
            v-else-if="
              item.run_status === 'completed' &&
              item.result_state === 'available' &&
              item.run_id !== null &&
              item.group_index !== null
            "
            class="secondary leave-result-action"
            type="button"
            @click="openResult(item.run_id, item.group_index)"
          >
            下载盖章材料
          </button>
        </div>
      </div>
    </section>
  </template>

  <template v-else-if="isAdmin">
    <section class="leave-admin-heading">
      <h2>汇总管理</h2>
      <p v-if="config">每天 {{ config.daily_cutoff }} 自动汇总 · Asia/Shanghai</p>
      <p v-if="summary && summary.todo_count" class="leave-admin-todo">
        待处理 · 待下载 {{ summary.ready_count }} · 待回传 {{ summary.awaiting_return_count }}
      </p>
    </section>

    <p v-if="config && !config.contact_phone_configured" class="leave-feedback leave-error">
      请假材料联系电话未配置，暂时无法下载材料。
    </p>

    <section v-if="readyRuns.length" class="leave-ready-section">
      <div class="section-heading"><h2>待下载 <span>· {{ readyRuns.length }}</span></h2></div>
      <article v-for="run in readyRuns" :key="run.id" class="leave-ready-run">
        <header class="leave-run-heading">
          <div>
            <strong>{{ formatCollectedAt(run.collected_at) }}</strong>
            <span>{{ run.member_count }} 人 · {{ run.groups.length }} 个时间组</span>
          </div>
          <span v-if="isSupplementRun(run)" class="leave-run-note">补充批次</span>
        </header>

        <div class="leave-run-row leave-reason-summary">
          <div><span class="leave-field-label">事由</span><p>{{ run.reason }}</p></div>
          <details class="leave-more">
            <summary aria-label="更多管理操作">···</summary>
            <div class="leave-more-menu">
              <button type="button" :disabled="actionRunId === run.id" @click="startReasonEdit(run, $event)">修改统一事由</button>
              <button class="leave-danger-action" type="button" :disabled="actionRunId === run.id" @click="cancelRun(run, $event)">取消本次汇总</button>
            </div>
          </details>
        </div>

        <div v-if="editingReasonRunId === run.id" class="leave-reason-editor">
          <textarea v-model="reasonDrafts[run.id]" rows="3" maxlength="500" aria-label="统一事由" />
          <div class="leave-inline-actions">
            <button type="button" @click="cancelReasonEdit(run)">取消</button>
            <button class="primary" type="button" :disabled="actionRunId === run.id" @click="saveReason(run)">保存事由</button>
          </div>
        </div>

        <div class="leave-run-groups">
          <div v-for="group in run.groups" :key="group.index" class="leave-group">
            <div class="leave-group-heading">
              <div><strong>{{ group.time_text }}</strong><span>{{ group.count }} 人</span></div>
              <button type="button" @click="togglePreview(run.id, group.index)">
                {{ previewKey === run.id + ':' + group.index ? "收起名单" : "名单" }}
              </button>
            </div>
            <div v-if="previewKey === run.id + ':' + group.index" class="leave-preview">
              <div v-for="member in group.members" :key="member.member_id" class="leave-preview-row">
                <span>{{ member.name }}</span><span>{{ member.student_id }}</span>
              </div>
            </div>
          </div>
        </div>

        <footer class="leave-run-actions">
          <button
            class="primary leave-run-download"
            type="button"
            :disabled="!run.document_ready || actionRunId === run.id"
            @click="downloadRunDocument(run)"
          >
            下载请假材料
          </button>
        </footer>
      </article>
    </section>

    <section v-if="awaitingReturnRuns.length" class="leave-awaiting-section">
      <div class="section-heading"><h2>待老师回传 <span>· {{ awaitingReturnRuns.length }}</span></h2></div>
      <article v-for="run in awaitingReturnRuns" :key="run.id" class="leave-ready-run">
        <header class="leave-run-heading">
          <div>
            <strong>{{ formatCollectedAt(run.collected_at) }}</strong>
            <span>{{ run.member_count }} 人 · {{ run.groups.length }} 个时间组</span>
            <span v-if="run.downloaded_at">
              {{ run.downloaded_by?.name || "管理员" }} · {{ formatDateTime(run.downloaded_at) }} 下载
            </span>
          </div>
          <span v-if="isSupplementRun(run)" class="leave-run-note">补充批次</span>
        </header>

        <div class="leave-run-groups">
          <div v-for="group in run.groups" :key="group.index" class="leave-group">
            <div class="leave-group-heading">
              <div>
                <strong>{{ group.time_text }}</strong>
                <span>{{ group.count }} 人</span>
                <span v-if="group.result?.available">已上传</span>
                <span v-else-if="group.result">材料已清理</span>
              </div>
              <div class="leave-group-actions">
                <button type="button" @click="togglePreview(run.id, group.index)">
                  {{ previewKey === run.id + ':' + group.index ? "收起名单" : "名单" }}
                </button>
                <button
                  v-if="group.result?.available"
                  type="button"
                  @click="openResult(run.id, group.index)"
                >
                  查看
                </button>
                <label class="secondary leave-upload-action">
                  {{ group.result?.available ? "重新上传" : "上传盖章结果" }}
                  <input
                    type="file"
                    accept=".jpg,.jpeg,.png,.pdf,image/jpeg,image/png,application/pdf"
                    :disabled="actionRunId === run.id"
                    @change="uploadResult(run, group.index, $event)"
                  />
                </label>
              </div>
            </div>
            <div v-if="previewKey === run.id + ':' + group.index" class="leave-preview">
              <div v-for="member in group.members" :key="member.member_id" class="leave-preview-row">
                <span>{{ member.name }}</span><span>{{ member.student_id }}</span>
              </div>
            </div>
          </div>
        </div>

        <footer class="leave-run-actions">
          <button
            class="secondary leave-run-download"
            type="button"
            :disabled="!run.document_ready || actionRunId === run.id"
            @click="downloadRunDocument(run)"
          >
            重新下载请假材料
          </button>
        </footer>
      </article>
    </section>

    <section v-if="pendingAdminRequests.length" class="leave-pending-section">
      <div class="section-heading leave-pending-heading">
        <div>
          <h2>待汇总 <span>· {{ pendingMemberCount }} 人</span></h2>
          <small v-if="config">每日 {{ config.daily_cutoff }} 自动汇总</small>
        </div>
        <button class="primary leave-collect" type="button" :disabled="actionRunId !== null" @click="collectNow">立即汇总</button>
      </div>
      <div v-for="day in pendingPreviewDays" :key="day.date" class="leave-pending-day">
        <h3>{{ formatMonthDay(day.date) }}</h3>
        <div class="leave-list">
          <div v-for="group in day.groups" :key="group.key" class="leave-group leave-pending-group">
            <div class="leave-group-heading">
              <div><strong>{{ formatTimeSpan(group.startAt, group.endAt) }}</strong><span>{{ group.requests.length }} 人</span></div>
              <button type="button" @click="togglePendingPreview(group.key)">
                {{ pendingPreviewKey === group.key ? "收起名单" : "名单" }}
              </button>
            </div>
            <div v-if="pendingPreviewKey === group.key" class="leave-preview">
              <div v-for="request in group.requests" :key="request.id" class="leave-preview-row">
                <span>{{ request.member_name_snapshot }}</span><span>{{ request.student_id_snapshot }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section
      v-if="!loading && readyRuns.length === 0 && awaitingReturnRuns.length === 0 && pendingAdminRequests.length === 0"
      class="leave-current-empty"
    >
      <span>当前没有需要处理的请假。</span>
      <button type="button" :disabled="actionRunId !== null" @click="collectNow">立即汇总</button>
    </section>

    <section class="leave-history-section">
      <div class="section-heading">
        <h2>已完成</h2>
        <button v-if="completedRuns.length > 3" type="button" @click="historyExpanded = !historyExpanded">
          {{ historyExpanded ? "收起" : "查看全部历史" }}
        </button>
      </div>
      <div v-if="completedRuns.length === 0" class="leave-empty">暂无记录</div>
      <div v-else class="leave-history-list">
        <details v-for="run in visibleCompletedRuns" :key="run.id" class="leave-history-run">
          <summary>
            <div>
              <strong>{{ formatDateTime(run.downloaded_at || run.collected_at) }} · {{ run.member_count }} 人 · {{ run.groups.length }} 个时间组</strong>
              <span>已完成<span v-if="isSupplementRun(run)"> · 补充批次</span></span>
            </div>
            <span class="leave-history-chevron" aria-hidden="true">›</span>
          </summary>
          <div class="leave-history-detail">
            <div v-for="group in run.groups" :key="group.index" class="leave-history-group">
              <div>
                <strong>{{ group.time_text }}</strong>
                <span>{{ group.count }} 人 · {{ group.result?.available ? "盖章材料可用" : "材料已清理" }}</span>
              </div>
              <div class="leave-group-actions">
                <button
                  v-if="group.result?.available"
                  type="button"
                  @click="openResult(run.id, group.index)"
                >
                  查看
                </button>
                <label class="secondary leave-upload-action">
                  重新上传
                  <input
                    type="file"
                    accept=".jpg,.jpeg,.png,.pdf,image/jpeg,image/png,application/pdf"
                    :disabled="actionRunId === run.id"
                    @change="uploadResult(run, group.index, $event)"
                  />
                </label>
              </div>
            </div>
            <div class="leave-history-actions">
              <button
                class="secondary leave-history-download"
                type="button"
                :disabled="!run.document_ready || actionRunId === run.id"
                @click="downloadRunDocument(run)"
              >
                下载请假材料
              </button>
              <details class="leave-more">
                <summary aria-label="更多历史操作">···</summary>
                <div class="leave-more-menu">
                  <button
                    class="leave-danger-action"
                    type="button"
                    :disabled="actionRunId === run.id"
                    @click="deleteRun(run, $event)"
                  >
                    删除记录
                  </button>
                </div>
              </details>
            </div>
          </div>
        </details>
      </div>
    </section>
  </template>
</template>

<style scoped>
.leave-page-title { margin-bottom: 0; }
.leave-view-tabs { display: flex; gap: 20px; margin-bottom: 24px; border-bottom: 1px solid var(--line); }
.leave-view-tabs button { border: 0; border-bottom: 2px solid transparent; border-radius: 0; background: transparent; padding: 10px 1px 9px; color: var(--muted); font-size: 13px; }
.leave-view-tabs button:hover, .leave-view-tabs button.active { color: var(--text); }
.leave-view-tabs button.active { border-bottom-color: var(--text); }

.leave-submit-section, .leave-my-requests, .leave-ready-section, .leave-awaiting-section, .leave-pending-section, .leave-history-section { margin-bottom: 30px; }
.leave-request-form { display: grid; gap: 9px; padding-bottom: 26px; border-bottom: 1px solid var(--line); }
.leave-form-controls { display: grid; grid-template-columns: minmax(150px, 1.1fr) minmax(250px, 1.6fr) auto; align-items: end; gap: 12px; }
.leave-form-controls label, .leave-time-pair label { min-width: 0; display: grid; gap: 6px; color: var(--muted); font-size: 12.5px; }
.leave-form-controls input { width: 100%; min-width: 0; }
.leave-time-pair { min-width: 0; display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); align-items: end; gap: 9px; }
.leave-time-arrow { padding-bottom: 9px; color: var(--faint); }
.leave-submit, .leave-collect { width: fit-content; white-space: nowrap; }
.leave-help, .leave-empty, .leave-admin-heading p, .leave-pending-heading small, .leave-row span, .leave-run-heading span, .leave-group-heading span, .leave-history-run span { color: var(--muted); font-size: 13px; }
.leave-help { margin: 0; line-height: 1.55; }
.leave-empty { padding: 10px 0; }

.leave-feedback { margin: 14px 0 18px; padding: 4px 0 4px 10px; border-left: 2px solid var(--line-strong); font-size: 13px; line-height: 1.55; }
.leave-error { border-left-color: var(--danger); color: var(--danger); }
.leave-success { border-left-color: var(--success); color: var(--success); }
.leave-inline-notice, .leave-current-empty { display: flex; align-items: center; justify-content: space-between; gap: 14px; margin: 0 0 24px; padding: 9px 0; border-bottom: 1px solid var(--line); color: var(--secondary); font-size: 13px; }

.leave-inline-notice button, .leave-current-empty button, .leave-history-section .section-heading > button, .leave-group-heading > button, .leave-inline-actions > button:first-child {
  border: 0; background: transparent; padding: 4px 0; color: var(--muted);
}
.leave-inline-notice button:hover, .leave-current-empty button:hover, .leave-history-section .section-heading > button:hover, .leave-group-heading > button:hover, .leave-inline-actions > button:first-child:hover { color: var(--text); }

.leave-list, .leave-history-list { border: 1px solid var(--line); background: var(--surface); }
.leave-row { min-width: 0; min-height: 54px; display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 10px 12px; }
.leave-row + .leave-row { border-top: 1px solid var(--line); }
.leave-row-main { min-width: 0; display: grid; gap: 3px; }
.leave-row-main strong { overflow-wrap: anywhere; }
.leave-row-muted { opacity: 0.58; }
.leave-row-actions { flex: 0 0 auto; }
.leave-group-actions { flex: 0 0 auto; display: flex; align-items: center; justify-content: flex-end; gap: 8px; flex-wrap: wrap; }
.leave-group-actions button { white-space: nowrap; }
.leave-upload-action { display: inline-flex; align-items: center; width: fit-content; white-space: nowrap; cursor: pointer; }
.leave-upload-action input { display: none; }
.leave-result-action { flex: 0 0 auto; white-space: nowrap; }

.leave-admin-heading { margin: 0 0 22px; }
.leave-admin-heading h2, .leave-admin-heading p { margin: 0; }
.leave-admin-heading p { margin-top: 4px; }
.section-heading h2 span { color: var(--faint); font-size: 13px; font-weight: 500; }

.leave-ready-run { border: 1px solid var(--line-strong); background: var(--surface); }
.leave-ready-run + .leave-ready-run { margin-top: 14px; }
.leave-run-heading, .leave-run-row, .leave-group-heading, .leave-preview-row, .leave-history-group { min-width: 0; display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.leave-run-heading { align-items: flex-start; padding: 14px; border-bottom: 1px solid var(--line); }
.leave-run-heading > div, .leave-group-heading > div, .leave-history-group > div { min-width: 0; display: grid; gap: 3px; }
.leave-run-note { flex: 0 0 auto; color: var(--faint); font-size: 12px; }
.leave-run-row { padding: 12px 14px; border-bottom: 1px solid var(--line); }
.leave-reason-summary > div:first-child { min-width: 0; }
.leave-field-label { display: block; margin-bottom: 4px; color: var(--faint); font-size: 11.5px; }
.leave-reason-summary p { margin: 0; color: var(--secondary); font-size: 13px; line-height: 1.6; overflow-wrap: anywhere; white-space: pre-wrap; }

.leave-more { position: relative; flex: 0 0 auto; }
.leave-more summary { width: 30px; height: 30px; display: grid; place-items: center; border-radius: 4px; color: var(--muted); cursor: pointer; list-style: none; user-select: none; }
.leave-more summary::-webkit-details-marker { display: none; }
.leave-more summary:hover { background: var(--hover); color: var(--text); }
.leave-more-menu { position: absolute; z-index: 5; top: calc(100% + 4px); right: 0; width: 190px; max-width: calc(100vw - 32px); display: grid; padding: 4px; border: 1px solid var(--line-strong); background: var(--surface); }
.leave-more-menu button { min-width: 0; border: 0; background: transparent; padding: 8px 9px; text-align: left; color: var(--secondary); }
.leave-more-menu button:hover { background: var(--hover); color: var(--text); }
.leave-more-menu .leave-danger-action { color: var(--danger); }

.leave-reason-editor { display: grid; gap: 8px; padding: 12px 14px; border-bottom: 1px solid var(--line); }
.leave-reason-editor textarea { width: 100%; min-width: 0; resize: vertical; }
.leave-inline-actions { display: flex; justify-content: flex-end; gap: 10px; }
.leave-run-groups { border-bottom: 1px solid var(--line); }
.leave-group { min-width: 0; padding: 11px 14px; }
.leave-group + .leave-group { border-top: 1px solid var(--line); }
.leave-group-heading strong { white-space: pre-line; }
.leave-preview { margin-top: 9px; padding-top: 4px; border-top: 1px solid var(--line); }
.leave-preview-row { padding: 7px 0; font-size: 13px; }
.leave-preview-row span { min-width: 0; overflow-wrap: anywhere; }
.leave-preview-row + .leave-preview-row { border-top: 1px solid var(--line); }

.leave-run-actions { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px 14px; }
.leave-run-download, .leave-history-download { width: fit-content; white-space: nowrap; }

.leave-pending-heading { align-items: flex-end; }
.leave-pending-heading > div { display: grid; gap: 3px; }
.leave-pending-day + .leave-pending-day { margin-top: 18px; }
.leave-pending-day h3 { margin: 0 0 7px; color: var(--secondary); font-size: 13px; font-weight: 560; }
.leave-pending-group { padding: 10px 12px; }
.leave-current-empty { margin-bottom: 28px; }

.leave-history-run + .leave-history-run { border-top: 1px solid var(--line); }
.leave-history-run > summary { min-width: 0; display: flex; align-items: center; justify-content: space-between; gap: 14px; padding: 11px 12px; cursor: pointer; list-style: none; }
.leave-history-run > summary::-webkit-details-marker { display: none; }
.leave-history-run > summary:hover { background: var(--hover); }
.leave-history-run > summary > div { min-width: 0; display: grid; gap: 3px; }
.leave-history-run > summary strong { overflow-wrap: anywhere; }
.leave-history-chevron { flex: 0 0 auto; color: var(--faint); font-size: 18px; transition: transform 120ms ease; }
.leave-history-run[open] .leave-history-chevron { transform: rotate(90deg); }
.leave-history-detail { border-top: 1px solid var(--line); padding: 0 12px 10px; }
.leave-history-group { padding: 9px 0; }
.leave-history-group + .leave-history-group { border-top: 1px solid var(--line); }
.leave-history-actions { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding-top: 10px; border-top: 1px solid var(--line); }

@media (max-width: 768px) {
  .leave-form-controls { grid-template-columns: minmax(138px, 1fr) minmax(230px, 1.5fr) auto; gap: 9px; }
}
@media (max-width: 520px) {
  .leave-view-tabs { gap: 16px; margin-bottom: 20px; }
  .leave-form-controls { grid-template-columns: minmax(0, 1fr); }
  .leave-time-pair { grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); }
  .leave-submit { justify-self: start; }
  .leave-inline-notice, .leave-current-empty, .leave-pending-heading, .leave-run-actions { align-items: flex-start; flex-direction: column; }
  .leave-history-actions { align-items: flex-start; }
  .leave-row, .leave-run-heading, .leave-group-heading, .leave-history-group { align-items: flex-start; }
  .leave-group-actions { justify-content: flex-start; }
  .leave-preview-row { gap: 10px; }
  .leave-preview-row span:last-child { text-align: right; }
  .leave-more-menu { width: min(190px, calc(100vw - 32px)); }
}
@media (max-width: 380px) {
  .leave-time-pair { grid-template-columns: minmax(0, 1fr); }
  .leave-time-arrow { display: none; }
  .leave-row, .leave-group-heading, .leave-preview-row, .leave-history-group { flex-direction: column; }
  .leave-preview-row span:last-child { text-align: left; }
}
</style>
