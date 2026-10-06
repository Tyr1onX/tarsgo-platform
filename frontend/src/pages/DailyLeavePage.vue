<script setup lang="ts">
import { computed, onMounted, ref } from "vue"

import { api } from "../api"
import ActionMenu, { type ActionMenuItem } from "../components/ActionMenu.vue"
import ConfirmDialog from "../components/ConfirmDialog.vue"
import LegacySchoolLeaveHistory from "./LegacySchoolLeaveHistory.vue"
import type { DailyLeaveWindowAdmin, DailyLeaveWindowMember, Member } from "../types"

const props = defineProps<{ currentUser: Member }>()
const emit = defineEmits<{ navigate: [path: string]; todoCount: [count: number] }>()

interface CloseRequest {
  title: string
  description: string
  confirmLabel: string
  action: () => Promise<void>
}

const memberWindows = ref<DailyLeaveWindowMember[]>([])
const adminWindows = ref<DailyLeaveWindowAdmin[]>([])
const loading = ref(true)
const saving = ref(false)
const downloadingId = ref<number | null>(null)
const error = ref("")
const notice = ref("")
const legacyExpanded = ref(false)
const closeRequest = ref<CloseRequest | null>(null)
const closePending = ref(false)
const draft = ref({
  title: "",
  start_at: "",
  end_at: "",
  open_until: "",
  team_open: true,
  public_enabled: false,
})

const isAdmin = computed(() => props.currentUser.role === "admin")
const profileReady = computed(() =>
  props.currentUser.name.trim().length >= 2 && props.currentUser.name.trim().length <= 50 &&
  /^[0-9]{8}$/.test(props.currentUser.student_id ?? "") &&
  Boolean(props.currentUser.college) &&
  (props.currentUser.team_membership === "formal" || props.currentUser.team_membership === "reserve"),
)

function messageOf(reason: unknown) {
  return reason instanceof Error ? reason.message : "操作失败"
}

function dateTime(value: string) {
  return value.slice(0, 16).replace("T", " ")
}

function range(window: Pick<DailyLeaveWindowMember, "start_at" | "end_at">) {
  return `${dateTime(window.start_at)} 至 ${dateTime(window.end_at)}`
}

function isWindowOpen(window: Pick<DailyLeaveWindowAdmin, "status" | "accepting_participants">) {
  return window.status === "open" && window.accepting_participants
}

function absolutePublicLink(leaveWindow: DailyLeaveWindowAdmin) {
  return leaveWindow.public_path ? new URL(leaveWindow.public_path, window.location.origin).toString() : ""
}

async function load() {
  loading.value = true
  error.value = ""
  try {
    const [mine, admin] = await Promise.all([
      api.dailyLeaveWindows(),
      isAdmin.value ? api.dailyLeaveAdminWindows() : Promise.resolve([]),
    ])
    memberWindows.value = mine
    adminWindows.value = admin
  } catch (reason) {
    error.value = messageOf(reason)
  } finally {
    loading.value = false
  }
  emit("todoCount", 0)
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

async function download(window: DailyLeaveWindowMember, offline = false) {
  downloadingId.value = window.id
  error.value = ""
  notice.value = ""
  try {
    const file = await api.downloadDailyLeaveDocument(window.id, offline)
    saveBlob(file.blob, file.filename)
    notice.value = offline ? "线下签章版已下载。" : "请假条已下载。"
  } catch (reason) {
    error.value = messageOf(reason)
  } finally {
    downloadingId.value = null
  }
}

function memberMenuActions(window: DailyLeaveWindowMember): ActionMenuItem[] {
  return [{ key: "offline", label: "下载线下签章版", disabled: downloadingId.value === window.id }]
}

function handleMemberMenu(window: DailyLeaveWindowMember, action: string) {
  if (action === "offline") void download(window, true)
}

async function createWindow() {
  saving.value = true
  error.value = ""
  notice.value = ""
  try {
    const created = await api.createDailyLeaveWindow({
      title: draft.value.title.trim(),
      start_at: draft.value.start_at,
      end_at: draft.value.end_at,
      open_until: draft.value.open_until,
      team_open: draft.value.team_open,
      public_enabled: draft.value.public_enabled,
    })
    notice.value = "请假窗口已授权开放。"
    draft.value = { title: "", start_at: "", end_at: "", open_until: "", team_open: true, public_enabled: false }
    await load()
    if (created.public_path) {
      notice.value = "请假窗口已授权开放，临时链接已生成。"
    }
  } catch (reason) {
    error.value = messageOf(reason)
  } finally {
    saving.value = false
  }
}

async function copyPublicLink(window: DailyLeaveWindowAdmin) {
  const link = absolutePublicLink(window)
  if (!link) return
  try {
    await navigator.clipboard.writeText(link)
    notice.value = "临时公开链接已复制。"
  } catch {
    notice.value = `临时公开链接：${link}`
  }
}

function closeMenuActions(window: DailyLeaveWindowAdmin): ActionMenuItem[] {
  return isWindowOpen(window)
    ? [{ key: "close", label: "关闭请假窗口", danger: true }]
    : []
}

function handleAdminMenu(window: DailyLeaveWindowAdmin, action: string) {
  if (action !== "close") return
  closeRequest.value = {
    title: "关闭请假窗口？",
    description: "关闭后，队内成员和公开链接都不能继续生成材料。",
    confirmLabel: "关闭窗口",
    action: async () => {
      await api.closeDailyLeaveWindow(window.id)
      notice.value = "请假窗口已关闭。"
      await load()
    },
  }
}

async function confirmClose() {
  const pending = closeRequest.value
  if (!pending || closePending.value) return
  closePending.value = true
  error.value = ""
  try {
    await pending.action()
  } catch (reason) {
    error.value = messageOf(reason)
  } finally {
    closePending.value = false
    closeRequest.value = null
  }
}

onMounted(load)
</script>

<template>
  <ConfirmDialog
    :open="closeRequest !== null"
    :title="closeRequest?.title ?? ''"
    :description="closeRequest?.description ?? ''"
    :confirm-label="closeRequest?.confirmLabel ?? '确认'"
    danger
    :pending="closePending"
    @cancel="closePending ? undefined : (closeRequest = null)"
    @confirm="confirmClose"
  />

  <div class="daily-leave-page">
    <p v-if="error" class="daily-leave-feedback daily-leave-error" role="alert">{{ error }}</p>
    <p v-if="notice" class="daily-leave-feedback daily-leave-notice" role="status">{{ notice }}</p>

    <section v-if="isAdmin || profileReady" class="daily-leave-section">
      <div class="daily-leave-heading"><h2>{{ isAdmin ? "我可以使用的窗口" : "当前开放窗口" }}</h2></div>
      <p v-if="loading" class="daily-leave-muted" role="status">正在加载…</p>
      <p v-else-if="!memberWindows.length" class="daily-leave-muted">当前没有开放的请假窗口。</p>
      <div v-else class="daily-leave-list">
        <article v-for="window in memberWindows" :key="window.id" class="daily-leave-row">
          <div class="daily-leave-main">
            <strong>{{ window.title }}</strong>
            <span>{{ range(window) }}</span>
            <small>开放至 {{ dateTime(window.open_until) }}</small>
          </div>
          <div class="daily-leave-actions">
            <button class="text-action" type="button" :disabled="downloadingId === window.id" @click="download(window)">
              {{ downloadingId === window.id ? "正在生成…" : "下载请假条" }}
            </button>
            <ActionMenu
              :id="`daily-window-${window.id}`"
              aria-label="其他下载选项"
              :disabled="downloadingId === window.id"
              :actions="memberMenuActions(window)"
              @select="handleMemberMenu(window, $event)"
            />
          </div>
        </article>
      </div>
      <p v-if="!profileReady" class="daily-leave-muted">
        请先完善姓名、8 位学号、学院和队内身份后使用请假窗口。
        <button class="text-action" type="button" @click="emit('navigate', '/me/edit')">去完善资料</button>
      </p>
    </section>

    <section v-if="isAdmin" class="daily-leave-section">
      <div class="daily-leave-heading"><h2>创建请假窗口</h2></div>
      <form class="daily-leave-create-form" @submit.prevent="createWindow">
        <label class="daily-leave-title-field">
          <span>活动名称</span>
          <input v-model="draft.title" maxlength="100" required autocomplete="off" placeholder="例如：校赛集中训练" />
        </label>
        <label>
          <span>开始时间</span>
          <input v-model="draft.start_at" type="datetime-local" required />
        </label>
        <label>
          <span>结束时间</span>
          <input v-model="draft.end_at" type="datetime-local" required />
        </label>
        <label>
          <span>开放截止时间</span>
          <input v-model="draft.open_until" type="datetime-local" required />
        </label>
        <div class="daily-leave-options">
          <label><input v-model="draft.team_open" type="checkbox" /> 对队内成员开放</label>
          <label><input v-model="draft.public_enabled" type="checkbox" /> 开启临时公开链接</label>
        </div>
        <button class="primary daily-leave-submit" type="submit" :disabled="saving">
          {{ saving ? "正在开放…" : "授权并开放" }}
        </button>
      </form>
    </section>

    <section v-if="isAdmin" class="daily-leave-section">
      <div class="daily-leave-heading"><h2>窗口管理</h2></div>
      <p v-if="loading" class="daily-leave-muted" role="status">正在加载…</p>
      <p v-else-if="!adminWindows.length" class="daily-leave-muted">还没有请假窗口。</p>
      <div v-else class="daily-leave-list">
        <article v-for="window in adminWindows" :key="window.id" class="daily-leave-row daily-leave-admin-row">
          <div class="daily-leave-main">
            <strong>{{ window.title }}</strong>
            <span>{{ range(window) }} · {{ window.status === "closed" ? "已关闭" : window.accepting_participants ? "开放中" : "已截止" }}</span>
            <small>{{ window.entry_count }} 份材料 · {{ window.team_open ? "队内开放" : "仅临时链接" }}<template v-if="window.public_enabled"> · 有临时公开链接</template></small>
            <div v-if="window.public_path" class="daily-leave-link">
              <a :href="window.public_path" target="_blank" rel="noreferrer">{{ absolutePublicLink(window) }}</a>
              <button class="text-action" type="button" @click="copyPublicLink(window)">复制链接</button>
            </div>
          </div>
          <ActionMenu
            :id="`daily-window-admin-${window.id}`"
            aria-label="窗口管理操作"
            :actions="closeMenuActions(window)"
            @select="handleAdminMenu(window, $event)"
          />
        </article>
      </div>
    </section>

    <section class="daily-leave-section daily-leave-legacy">
      <div class="daily-leave-heading">
        <h2>旧版日常请假历史</h2>
        <button class="text-action" type="button" :aria-expanded="legacyExpanded" @click="legacyExpanded = !legacyExpanded">
          {{ legacyExpanded ? "收起" : "查看历史（只读）" }}
        </button>
      </div>
      <LegacySchoolLeaveHistory v-if="legacyExpanded" :current-user="props.currentUser" />
    </section>
  </div>
</template>

<style scoped>
.daily-leave-page { min-width: 0; max-width: 100%; }
.daily-leave-section { min-width: 0; margin-top: 24px; }
.daily-leave-section:first-child { margin-top: 0; }
.daily-leave-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 8px; }
.daily-leave-heading h2 { margin: 0; font-size: 15px; font-weight: 620; }
.daily-leave-feedback { margin: 0 0 12px; font-size: 13px; overflow-wrap: anywhere; }
.daily-leave-error { color: var(--danger); }
.daily-leave-notice { color: var(--success, #23744b); }
.daily-leave-muted { margin: 7px 0; color: var(--faint); font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }
.daily-leave-list { min-width: 0; border-top: 1px solid var(--line); }
.daily-leave-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; min-width: 0; padding: 11px 0; border-bottom: 1px solid var(--line); }
.daily-leave-main { display: grid; gap: 4px; min-width: 0; }
.daily-leave-main strong { font-size: 14px; font-weight: 560; overflow-wrap: anywhere; }
.daily-leave-main span { font-size: 12px; color: var(--muted); overflow-wrap: anywhere; }
.daily-leave-main small { color: var(--faint); font-size: 12px; overflow-wrap: anywhere; }
.daily-leave-actions { display: flex; align-items: center; gap: 10px; flex: 0 0 auto; }
.daily-leave-actions button { padding: 2px 0; white-space: nowrap; }
.daily-leave-create-form { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 11px 13px; max-width: 720px; }
.daily-leave-create-form label { display: grid; min-width: 0; gap: 5px; color: var(--muted); font-size: 12px; }
.daily-leave-create-form input:not([type="checkbox"]) { box-sizing: border-box; width: 100%; min-width: 0; }
.daily-leave-title-field, .daily-leave-options { grid-column: 1 / -1; }
.daily-leave-options { display: flex; flex-wrap: wrap; gap: 8px 18px; }
.daily-leave-options label { display: flex; align-items: center; gap: 7px; }
.daily-leave-submit { justify-self: start; }
.daily-leave-link { display: flex; flex-wrap: wrap; gap: 4px 12px; min-width: 0; align-items: baseline; }
.daily-leave-link a { color: var(--secondary); font-size: 12px; overflow-wrap: anywhere; }
.daily-leave-link button { padding: 1px 0; white-space: nowrap; }
.daily-leave-legacy { padding-top: 15px; border-top: 1px solid var(--line); }
.daily-leave-legacy .daily-leave-heading button { padding: 2px 0; }
@media (max-width: 520px) {
  .daily-leave-row { display: grid; grid-template-columns: minmax(0, 1fr); gap: 7px; }
  .daily-leave-actions { justify-content: flex-start; }
  .daily-leave-create-form { grid-template-columns: minmax(0, 1fr); }
  .daily-leave-title-field, .daily-leave-options { grid-column: auto; }
}
</style>
