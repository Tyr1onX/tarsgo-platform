<script setup lang="ts">
import { computed, onMounted, ref } from "vue"

import { api } from "../api"
import type {
  Member,
  SchoolLeaveAdminConfig,
  SchoolLeaveRequest,
  SchoolLeaveRun,
} from "../types"

const props = defineProps<{ currentUser: Member }>()
const emit = defineEmits<{ navigate: [path: string] }>()

const requests = ref<SchoolLeaveRequest[]>([])
const adminRequests = ref<SchoolLeaveRequest[]>([])
const runs = ref<SchoolLeaveRun[]>([])
const config = ref<SchoolLeaveAdminConfig | null>(null)
const loading = ref(true)
const saving = ref(false)
const actionRunId = ref<number | null>(null)
const error = ref("")
const notice = ref("")
const editingRequestId = ref<number | null>(null)
const reasonDrafts = ref<Record<number, string>>({})
const previewKey = ref("")

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
const readyRuns = computed(() => runs.value.filter((item) => item.status === "ready"))
const sentRuns = computed(() => runs.value.filter((item) => item.status === "sent"))

function messageOf(reason: unknown) {
  return reason instanceof Error ? reason.message : "操作失败"
}

function toInputParts(value: string) {
  const [datePart, timePart = ""] = value.split("T")
  return { date: datePart, time: timePart.slice(0, 5) }
}

function formatDateTime(value: string | null) {
  if (!value) return ""
  return value.replace("T", " ").slice(0, 16)
}

function formatRange(item: Pick<SchoolLeaveRequest, "start_at" | "end_at">) {
  const start = toInputParts(item.start_at)
  const end = toInputParts(item.end_at)
  if (start.date === end.date) return `${start.date} · ${start.time}–${end.time}`
  return `${start.date} ${start.time} → ${end.date} ${end.time}`
}

function requestStatusLabel(status: SchoolLeaveRequest["status"]) {
  if (status === "pending") return "待汇总"
  if (status === "included") return "已汇总"
  return "已撤回"
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
      const [nextConfig, nextAdminRequests, nextRuns] = await Promise.all([
        api.schoolLeaveAdminConfig(),
        api.schoolLeaveAdminRequests(),
        api.schoolLeaveRuns(),
      ])
      config.value = nextConfig
      adminRequests.value = nextAdminRequests
      runs.value = nextRuns
      reasonDrafts.value = Object.fromEntries(nextRuns.map((run) => [run.id, run.reason]))
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

async function saveReason(run: SchoolLeaveRun) {
  actionRunId.value = run.id
  error.value = ""
  notice.value = ""
  try {
    await api.updateSchoolLeaveRunReason(run.id, reasonDrafts.value[run.id] ?? "")
    notice.value = "统一请假事由已更新。"
    await load()
  } catch (reason) {
    error.value = messageOf(reason)
  } finally {
    actionRunId.value = null
  }
}

async function cancelRun(run: SchoolLeaveRun) {
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

async function markSent(run: SchoolLeaveRun) {
  if (!window.confirm("确认已经通过微信或 QQ 私聊老师发送了这些材料？")) return
  actionRunId.value = run.id
  error.value = ""
  notice.value = ""
  try {
    await api.markSchoolLeaveRunSent(run.id)
    notice.value = "已记录为发送完成。"
    await load()
  } catch (reason) {
    error.value = messageOf(reason)
  } finally {
    actionRunId.value = null
  }
}

async function copyMessage(run: SchoolLeaveRun) {
  error.value = ""
  notice.value = ""
  try {
    await navigator.clipboard.writeText(run.send_message)
    notice.value = "发送文案已复制。"
  } catch {
    error.value = "复制失败，请手动选择发送文案。"
  }
}

function download(url: string) {
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.rel = "noopener"
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
}

function togglePreview(runId: number, groupIndex: number) {
  const key = `${runId}:${groupIndex}`
  previewKey.value = previewKey.value === key ? "" : key
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
  <div class="page-title">
    <h1>学校请假</h1>
  </div>

  <p v-if="error" class="leave-feedback leave-error">{{ error }}</p>
  <p v-if="notice" class="leave-feedback leave-success">{{ notice }}</p>

  <section v-if="!currentUser.student_id" class="leave-alert">
    <strong>请先完善学号，生成学校请假材料时需要使用。</strong>
    <button type="button" @click="emit('navigate', '/me')">去完善</button>
  </section>

  <form class="management-form leave-form" @submit.prevent="submitRequest">
    <div class="section-heading">
      <h2>{{ editingRequestId === null ? "提交请假" : "修改请假" }}</h2>
      <button v-if="editingRequestId !== null" type="button" @click="resetForm">取消修改</button>
    </div>
    <label>
      请假日期
      <input v-model="leaveDate" type="date" required />
    </label>
    <div class="leave-time-grid">
      <label>
        开始时间
        <input v-model="startTime" type="time" step="300" required />
      </label>
      <label>
        结束时间
        <input v-model="endTime" type="time" step="300" required />
      </label>
    </div>
    <p class="leave-help">相同请假时间会自动汇总到同一份请假材料中，请按自己的实际缺课时间填写。</p>
    <button class="primary" type="submit" :disabled="saving || !currentUser.student_id">
      {{ saving ? "正在保存…" : editingRequestId === null ? "提交请假" : "保存修改" }}
    </button>
  </form>

  <section>
    <div class="section-heading"><h2>我的申请</h2></div>
    <div v-if="loading" class="leave-empty">正在加载…</div>
    <div v-else-if="requests.length === 0" class="leave-empty">暂无请假申请。</div>
    <div v-else class="leave-list">
      <div v-for="item in requests" :key="item.id" class="leave-row">
        <div>
          <strong>{{ formatRange(item) }}</strong>
          <span>{{ requestStatusLabel(item.status) }}</span>
        </div>
        <div v-if="item.status === 'pending'" class="row-actions">
          <button type="button" @click="editRequest(item)">修改</button>
          <button class="danger-text" type="button" @click="withdrawRequest(item)">撤回</button>
        </div>
      </div>
    </div>
  </section>

  <template v-if="isAdmin">
    <section class="leave-admin">
      <div class="section-heading">
        <div>
          <h2>汇总管理</h2>
          <small v-if="config">每日 {{ config.daily_cutoff }} · Asia/Shanghai</small>
        </div>
        <button class="primary" type="button" :disabled="actionRunId !== null" @click="collectNow">立即汇总</button>
      </div>
      <p v-if="config && !config.contact_phone_configured" class="leave-feedback leave-error">
        LEAVE_CONTACT_PHONE 未配置，当前不能生成 DOCX。
      </p>
    </section>

    <section>
      <div class="section-heading"><h2>待汇总</h2><span>{{ pendingAdminRequests.length }}</span></div>
      <div v-if="pendingAdminRequests.length === 0" class="leave-empty">当前没有待汇总申请。</div>
      <div v-else class="leave-list">
        <div v-for="item in pendingAdminRequests" :key="item.id" class="leave-row leave-row-admin">
          <div>
            <strong>{{ item.member_name_snapshot }} · {{ item.student_id_snapshot }}</strong>
            <span>{{ formatRange(item) }}</span>
          </div>
        </div>
      </div>
    </section>

    <section>
      <div class="section-heading"><h2>待发送</h2><span>{{ readyRuns.length }}</span></div>
      <div v-if="readyRuns.length === 0" class="leave-empty">当前没有待发送批次。</div>
      <article v-for="run in readyRuns" :key="run.id" class="leave-run">
        <header class="leave-run-heading">
          <div>
            <strong>{{ formatDateTime(run.collected_at) }} 汇总</strong>
            <span>{{ run.member_count }} 人 · {{ run.groups.length }} 个时间组</span>
          </div>
          <small v-if="isSupplementRun(run)">补充批次</small>
        </header>

        <div class="leave-reason">
          <label>
            统一事由
            <textarea v-model="reasonDrafts[run.id]" rows="2" maxlength="500" />
          </label>
          <button type="button" :disabled="actionRunId === run.id" @click="saveReason(run)">保存事由</button>
        </div>

        <div v-for="group in run.groups" :key="group.index" class="leave-group">
          <div class="leave-group-heading">
            <div>
              <strong>{{ group.time_text }}</strong>
              <span>{{ group.count }} 人</span>
            </div>
            <div class="row-actions">
              <button type="button" @click="togglePreview(run.id, group.index)">预览</button>
              <button
                type="button"
                :disabled="!run.document_ready"
                @click="download(`/api/school-leave/admin/runs/${run.id}/documents/${group.index}`)"
              >下载 DOCX</button>
            </div>
          </div>
          <div v-if="previewKey === `${run.id}:${group.index}`" class="leave-preview">
            <div v-for="member in group.members" :key="member.member_id" class="leave-preview-row">
              <span>{{ member.name }}</span>
              <span>{{ member.student_id }}</span>
            </div>
          </div>
        </div>

        <div class="leave-message">{{ run.send_message }}</div>
        <div class="leave-run-actions">
          <button type="button" :disabled="!run.document_ready" @click="download(`/api/school-leave/admin/runs/${run.id}/documents.zip`)">
            下载全部
          </button>
          <button type="button" @click="copyMessage(run)">复制发送文案</button>
          <button class="primary" type="button" :disabled="actionRunId === run.id" @click="markSent(run)">标记已发送</button>
          <button class="danger-text" type="button" :disabled="actionRunId === run.id" @click="cancelRun(run)">取消本次汇总</button>
        </div>
      </article>
    </section>

    <section>
      <div class="section-heading"><h2>已发送</h2><span>{{ sentRuns.length }}</span></div>
      <div v-if="sentRuns.length === 0" class="leave-empty">暂无已发送批次。</div>
      <article v-for="run in sentRuns" :key="run.id" class="leave-run leave-run-sent">
        <header class="leave-run-heading">
          <div>
            <strong>{{ formatDateTime(run.collected_at) }} 汇总</strong>
            <span>{{ run.member_count }} 人 · {{ run.groups.length }} 个时间组</span>
          </div>
          <small>{{ formatDateTime(run.sent_at) }} · {{ run.sent_by?.name ?? "管理员" }}已标记发送</small>
        </header>
        <div v-for="group in run.groups" :key="group.index" class="leave-group leave-group-sent">
          <div class="leave-group-heading">
            <div>
              <strong>{{ group.time_text }}</strong>
              <span>{{ group.count }} 人</span>
            </div>
            <button
              type="button"
              :disabled="!run.document_ready"
              @click="download(`/api/school-leave/admin/runs/${run.id}/documents/${group.index}`)"
            >下载 DOCX</button>
          </div>
        </div>
      </article>
    </section>
  </template>
</template>

<style scoped>
.leave-form,
.leave-admin,
section {
  margin-bottom: 28px;
}

.leave-time-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.leave-help,
.leave-empty,
.leave-run span,
.leave-row span,
.leave-run small,
.leave-admin small {
  color: var(--muted);
  font-size: 13px;
}

.leave-help {
  margin: -4px 0 0;
  line-height: 1.6;
}

.leave-feedback,
.leave-alert {
  margin: 0 0 18px;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 4px;
  font-size: 13px;
}

.leave-error {
  border-color: color-mix(in srgb, #c43d3d 45%, var(--line));
}

.leave-success {
  border-color: color-mix(in srgb, #2f8f5b 45%, var(--line));
}

.leave-alert {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.leave-list,
.leave-run,
.leave-group,
.leave-preview {
  border-top: 1px solid var(--line);
}

.leave-row,
.leave-run-heading,
.leave-group-heading,
.leave-preview-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.leave-row {
  min-height: 58px;
  padding: 10px 0;
}

.leave-row > div:first-child,
.leave-run-heading > div,
.leave-group-heading > div {
  min-width: 0;
  display: grid;
  gap: 4px;
}

.leave-run {
  padding: 16px 0 22px;
}

.leave-run-heading {
  align-items: flex-start;
  margin-bottom: 14px;
}

.leave-reason {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: end;
  gap: 10px;
  margin-bottom: 12px;
}

.leave-reason label {
  display: grid;
  gap: 6px;
}

.leave-reason textarea {
  width: 100%;
  resize: vertical;
}

.leave-group {
  padding: 12px 0;
}

.leave-group-heading strong {
  white-space: pre-line;
}

.leave-preview {
  margin-top: 10px;
}

.leave-preview-row {
  padding: 8px 0;
  font-size: 13px;
}

.leave-preview-row + .leave-preview-row {
  border-top: 1px solid var(--line);
}

.leave-message {
  margin-top: 14px;
  padding: 10px 0;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.65;
}

.leave-run-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.leave-run-sent {
  opacity: 0.86;
}

@media (max-width: 520px) {
  .leave-time-grid {
    grid-template-columns: 1fr;
  }

  .leave-row,
  .leave-run-heading,
  .leave-group-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .leave-reason {
    grid-template-columns: 1fr;
  }

  .row-actions,
  .leave-run-actions {
    width: 100%;
    display: flex;
    flex-wrap: wrap;
  }

  .row-actions > *,
  .leave-run-actions > * {
    max-width: 100%;
  }
}
</style>
