<script setup lang="ts">
import { computed, onMounted, ref } from "vue"

import { api } from "../api"
import ConfirmDialog from "../components/ConfirmDialog.vue"
import type { CampLeaveAdminEvent, CampLeaveAdminEventDetail, CampLeaveEventMember, Member } from "../types"

const props = defineProps<{ currentUser: Member }>()
const emit = defineEmits<{ navigate: [path: string] }>()

interface Confirmation {
  title: string
  description: string
  confirmLabel: string
  danger?: boolean
  action: () => Promise<void>
}

const memberEvents = ref<CampLeaveEventMember[]>([])
const adminEvents = ref<CampLeaveAdminEvent[]>([])
const selectedEventId = ref<number | null>(null)
const selectedDetail = ref<CampLeaveAdminEventDetail | null>(null)
const loading = ref(true)
const saving = ref(false)
const detailLoading = ref(false)
const error = ref("")
const notice = ref("")
const confirmation = ref<Confirmation | null>(null)
const confirmationPending = ref(false)
const draft = ref({ title: "", type: "winter" as "winter" | "summer", start_date: "", end_date: "", collection_deadline: "" })

const isAdmin = computed(() => props.currentUser.role === "admin")
const profileReady = computed(() =>
  props.currentUser.name.trim().length >= 2 && props.currentUser.name.trim().length <= 50 &&
  /^[0-9]{8}$/.test(props.currentUser.student_id ?? "") &&
  Boolean(props.currentUser.college) &&
  (props.currentUser.team_membership === "formal" || props.currentUser.team_membership === "reserve"),
)
const activeEvents = computed(() => memberEvents.value.filter((event) =>
  event.status === "collecting" && (isAdmin.value || event.accepting_participants),
))
const historyEvents = computed(() => memberEvents.value.filter((event) =>
  event.status !== "collecting" || (!isAdmin.value && !event.accepting_participants),
))
const adminEventById = computed(() => new Map(adminEvents.value.map((event) => [event.id, event])))

function messageOf(reason: unknown) {
  return reason instanceof Error ? reason.message : "操作失败"
}

function typeLabel(type: "winter" | "summer") {
  return type === "winter" ? "冬令营" : "夏令营"
}

function identityLabel(type: "formal" | "reserve" | "other" | null) {
  if (type === "formal") return "正式队员"
  if (type === "reserve") return "梯队成员"
  if (type === "other") return "其他参与者"
  return ""
}

function eventStatusLabel(event: CampLeaveEventMember) {
  if (event.status === "closed") return "已关闭"
  return event.accepting_participants ? "收集中" : "报名已截止"
}

function dateSpan(start: string, end: string) {
  return start === end ? start : `${start} 至 ${end}`
}

function dateTime(value: string) {
  return value.slice(0, 16).replace("T", " ")
}

async function load() {
  loading.value = true
  error.value = ""
  try {
    const [mine, admin] = await Promise.all([
      api.campLeaveEvents(),
      isAdmin.value ? api.campLeaveAdminEvents() : Promise.resolve([]),
    ])
    memberEvents.value = mine
    adminEvents.value = admin
    if (selectedEventId.value !== null && !admin.some((event) => event.id === selectedEventId.value)) {
      selectedEventId.value = null
      selectedDetail.value = null
    }
  } catch (reason) {
    error.value = messageOf(reason)
  } finally {
    loading.value = false
  }
}

async function refreshEvent(eventId: number) {
  await load()
  if (isAdmin.value && selectedEventId.value === eventId) await showEvent(eventId)
}

async function toggleParticipation(event: CampLeaveEventMember) {
  if (saving.value || !event.accepting_participants) return
  if (!event.joined && !profileReady.value) {
    error.value = "请先完善个人资料中的姓名、学号、学院和队内身份。"
    return
  }
  saving.value = true
  error.value = ""
  notice.value = ""
  try {
    if (event.joined) await api.leaveCampLeaveEvent(event.id)
    else await api.joinCampLeaveEvent(event.id)
    notice.value = event.joined ? "已取消参加。" : "已确认参加。"
    await refreshEvent(event.id)
  } catch (reason) {
    error.value = messageOf(reason)
  } finally {
    saving.value = false
  }
}

async function showEvent(eventId: number) {
  selectedEventId.value = eventId
  detailLoading.value = true
  selectedDetail.value = null
  error.value = ""
  try {
    selectedDetail.value = await api.campLeaveAdminEvent(eventId)
  } catch (reason) {
    error.value = messageOf(reason)
  } finally {
    detailLoading.value = false
  }
}

function closeDetails() {
  selectedEventId.value = null
  selectedDetail.value = null
}

async function createEvent() {
  error.value = ""
  notice.value = ""
  saving.value = true
  try {
    const created = await api.createCampLeaveEvent({
      title: draft.value.title.trim(),
      type: draft.value.type,
      start_date: draft.value.start_date,
      end_date: draft.value.end_date,
      collection_deadline: draft.value.collection_deadline,
    })
    notice.value = "集中请假活动已创建。"
    draft.value = { title: "", type: "winter", start_date: "", end_date: "", collection_deadline: "" }
    await load()
    await showEvent(created.id)
  } catch (reason) {
    error.value = messageOf(reason)
  } finally {
    saving.value = false
  }
}

function askConfirmation(request: Confirmation) {
  confirmation.value = request
}

async function confirmAction() {
  const request = confirmation.value
  if (!request || confirmationPending.value) return
  confirmationPending.value = true
  try {
    await request.action()
  } catch (reason) {
    error.value = messageOf(reason)
  } finally {
    confirmationPending.value = false
    confirmation.value = null
  }
}

function closeEvent(event: CampLeaveAdminEvent) {
  askConfirmation({
    title: "关闭本次报名？",
    description: "关闭后，成员不能再参加或取消，管理员也不能移除名单记录。",
    confirmLabel: "关闭收集",
    danger: true,
    action: async () => {
      await api.closeCampLeaveEvent(event.id)
      notice.value = "报名收集已关闭。"
      await load()
      if (selectedEventId.value === event.id) await showEvent(event.id)
    },
  })
}

function removeParticipant(eventId: number, participantId: number, name: string) {
  askConfirmation({
    title: "移除这条报名？",
    description: `将从名单中移除${name}，此操作无法撤销。`,
    confirmLabel: "移除记录",
    danger: true,
    action: async () => {
      await api.removeCampLeaveParticipant(eventId, participantId)
      notice.value = "报名记录已移除。"
      await load()
      await showEvent(eventId)
    },
  })
}

async function copyPublicLink(event: CampLeaveAdminEvent) {
  const link = absolutePublicLink(event)
  try {
    await navigator.clipboard.writeText(link)
    notice.value = "公开报名链接已复制。"
  } catch {
    error.value = "复制失败，请使用页面显示的报名链接。"
  }
}

function absolutePublicLink(event: CampLeaveAdminEvent) {
  return new URL(event.public_path, window.location.origin).toString()
}

onMounted(load)
</script>

<template>
  <ConfirmDialog
    :open="confirmation !== null"
    :title="confirmation?.title ?? ''"
    :description="confirmation?.description ?? ''"
    :confirm-label="confirmation?.confirmLabel ?? '确认'"
    :danger="confirmation?.danger ?? false"
    :pending="confirmationPending"
    @cancel="confirmationPending ? undefined : (confirmation = null)"
    @confirm="confirmAction"
  />

  <div class="camp-leave-page">
    <p v-if="error" class="camp-feedback camp-error" role="alert">{{ error }}</p>
    <p v-if="notice" class="camp-feedback camp-success" role="status">{{ notice }}</p>

    <template v-if="loading">
      <p class="camp-muted" role="status">正在加载集中请假活动…</p>
    </template>
    <template v-else>
      <section class="camp-section">
        <div class="camp-section-heading"><h2>开放中的活动</h2></div>
        <p v-if="!activeEvents.length" class="camp-muted">当前没有开放活动。</p>
        <div v-else class="camp-event-list">
          <article v-for="event in activeEvents" :key="event.id" class="camp-event-row">
            <div class="camp-event-main">
              <div class="camp-event-titleline">
                <span class="camp-type">{{ typeLabel(event.type) }}</span>
                <h3>{{ event.title }}</h3>
              </div>
              <p>{{ dateSpan(event.start_date, event.end_date) }} · 截止 {{ dateTime(event.collection_deadline) }}</p>
              <p v-if="event.joined" class="camp-own-state">已确认参加<span v-if="event.participant_type"> · {{ identityLabel(event.participant_type) }}</span></p>
              <p v-else-if="!event.accepting_participants" class="camp-muted">报名已截止</p>
              <p v-if="isAdmin && adminEventById.get(event.id)" class="camp-muted">{{ adminEventById.get(event.id)?.participant_count }} 人已报名</p>
            </div>
            <div class="camp-event-actions">
              <button
                v-if="event.accepting_participants && (profileReady || event.joined)"
                class="text-action"
                type="button"
                :disabled="saving"
                @click="toggleParticipation(event)"
              >{{ saving ? "保存中…" : event.joined ? "取消参加" : "确认参加" }}</button>
              <button v-else-if="event.accepting_participants && !profileReady" class="text-action" type="button" @click="emit('navigate', '/me')">完善个人资料</button>
              <button v-if="isAdmin" class="text-action" type="button" @click="showEvent(event.id)">查看名单</button>
              <button v-if="isAdmin && event.status === 'collecting'" class="text-action" type="button" @click="closeEvent(adminEventById.get(event.id)!)">关闭收集</button>
            </div>
          </article>
        </div>
      </section>

      <section class="camp-section">
        <div class="camp-section-heading"><h2>历史活动</h2></div>
        <p v-if="!historyEvents.length" class="camp-muted">没有历史活动。</p>
        <div v-else class="camp-event-list">
          <article v-for="event in historyEvents" :key="event.id" class="camp-event-row">
            <div class="camp-event-main">
              <div class="camp-event-titleline">
                <span class="camp-type">{{ typeLabel(event.type) }}</span>
                <h3>{{ event.title }}</h3>
              </div>
              <p>{{ dateSpan(event.start_date, event.end_date) }} · {{ eventStatusLabel(event) }}</p>
              <p v-if="event.joined" class="camp-own-state">已确认参加<span v-if="event.participant_type"> · {{ identityLabel(event.participant_type) }}</span></p>
              <p v-if="isAdmin && adminEventById.get(event.id)" class="camp-muted">{{ adminEventById.get(event.id)?.participant_count }} 人已报名</p>
            </div>
            <div v-if="isAdmin" class="camp-event-actions">
              <button class="text-action" type="button" @click="showEvent(event.id)">查看名单</button>
            </div>
          </article>
        </div>
      </section>

      <section v-if="isAdmin" class="camp-section camp-create-section">
        <div class="camp-section-heading"><h2>创建集中请假活动</h2></div>
        <form class="camp-create-form" @submit.prevent="createEvent">
          <label class="camp-field camp-title-field">
            <span>活动名称</span>
            <input v-model="draft.title" required maxlength="100" autocomplete="off" placeholder="例如：2027 冬令营" />
          </label>
          <label class="camp-field">
            <span>活动类型</span>
            <select v-model="draft.type">
              <option value="winter">冬令营</option>
              <option value="summer">夏令营</option>
            </select>
          </label>
          <label class="camp-field">
            <span>开始日期</span>
            <input v-model="draft.start_date" type="date" required />
          </label>
          <label class="camp-field">
            <span>结束日期</span>
            <input v-model="draft.end_date" type="date" required />
          </label>
          <label class="camp-field">
            <span>收集截止时间（北京时间）</span>
            <input v-model="draft.collection_deadline" type="datetime-local" required />
          </label>
          <button class="primary camp-create-submit" type="submit" :disabled="saving">
            {{ saving ? "创建中…" : "创建活动" }}
          </button>
        </form>
      </section>

      <section v-if="isAdmin && selectedEventId !== null" class="camp-section camp-detail-section">
        <div class="camp-section-heading">
          <h2>{{ selectedDetail?.event.title ?? "活动名单" }}</h2>
          <button class="text-action" type="button" @click="closeDetails">收起</button>
        </div>
        <p v-if="detailLoading" class="camp-muted" role="status">正在加载名单…</p>
        <template v-else-if="selectedDetail">
          <div class="camp-link-row">
          <div><span class="camp-muted">公开报名链接</span><a :href="selectedDetail.event.public_path" target="_blank" rel="noreferrer">{{ absolutePublicLink(selectedDetail.event) }}</a></div>
            <button class="text-action" type="button" @click="copyPublicLink(selectedDetail.event)">复制链接</button>
          </div>
          <p v-if="!selectedDetail.groups.length" class="camp-muted">还没有报名记录。</p>
          <div v-for="group in selectedDetail.groups" :key="group.college" class="camp-college-group">
            <div class="camp-college-heading"><strong>{{ group.college_name }}</strong><span>{{ group.count }} 人</span></div>
            <div v-for="person in group.participants" :key="person.id" class="camp-person-row">
              <div><strong>{{ person.name }}</strong><span>{{ person.student_id }}</span><small>{{ identityLabel(person.participant_type) }}</small></div>
              <button v-if="selectedDetail.event.status === 'collecting' && selectedDetail.event.accepting_participants" class="text-action" type="button" @click="removeParticipant(selectedDetail.event.id, person.id, person.name)">移除</button>
            </div>
          </div>
          <p v-if="selectedDetail.event.status === 'closed' || !selectedDetail.event.accepting_participants" class="camp-muted">收集已结束，名单只读。</p>
        </template>
      </section>
    </template>
  </div>
</template>

<style scoped>
.camp-leave-page { min-width: 0; max-width: 100%; }
.camp-section { min-width: 0; margin-top: 26px; }
.camp-section:first-of-type { margin-top: 0; }
.camp-section-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 9px; }
.camp-section-heading h2 { margin: 0; font-size: 15px; font-weight: 620; }
.camp-event-list { min-width: 0; border-top: 1px solid var(--line); }
.camp-event-row { min-width: 0; display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; padding: 12px 0; border-bottom: 1px solid var(--line); }
.camp-event-main { min-width: 0; }
.camp-event-titleline { display: flex; align-items: baseline; gap: 8px; min-width: 0; }
.camp-event-titleline h3 { min-width: 0; margin: 0; font-size: 14px; font-weight: 570; overflow-wrap: anywhere; }
.camp-type { flex: 0 0 auto; color: var(--faint); font-size: 12px; }
.camp-event-main p { margin: 4px 0 0; color: var(--muted); font-size: 12px; line-height: 1.45; overflow-wrap: anywhere; }
.camp-event-main .camp-own-state { color: var(--text); }
.camp-muted { margin: 5px 0 0; color: var(--faint); font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }
.camp-event-actions { flex: 0 0 auto; display: flex; justify-content: flex-end; flex-wrap: wrap; gap: 4px 12px; padding-top: 2px; }
.camp-event-actions button, .camp-section-heading button { padding: 2px 0; white-space: nowrap; }
.camp-feedback { margin: 0 0 12px; font-size: 13px; }
.camp-error { color: var(--danger); }
.camp-success { color: var(--success, #23744b); }
.camp-create-form { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; max-width: 720px; }
.camp-field { display: grid; min-width: 0; gap: 5px; color: var(--muted); font-size: 12px; }
.camp-field input, .camp-field select { box-sizing: border-box; width: 100%; min-width: 0; }
.camp-title-field { grid-column: 1 / -1; }
.camp-create-submit { justify-self: start; }
.camp-detail-section { padding-top: 3px; }
.camp-link-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 9px 0 11px; border-bottom: 1px solid var(--line); }
.camp-link-row > div { display: grid; min-width: 0; gap: 3px; }
.camp-link-row a { color: var(--secondary); font-size: 12px; overflow-wrap: anywhere; }
.camp-link-row button { flex: 0 0 auto; }
.camp-college-group { min-width: 0; }
.camp-college-heading { display: flex; justify-content: space-between; gap: 12px; padding: 10px 0 5px; color: var(--secondary); font-size: 12px; }
.camp-college-heading span { color: var(--faint); }
.camp-person-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-width: 0; padding: 8px 0; border-top: 1px solid var(--line); }
.camp-person-row > div { display: flex; align-items: baseline; flex-wrap: wrap; gap: 4px 10px; min-width: 0; font-size: 13px; }
.camp-person-row strong { font-weight: 560; }
.camp-person-row span, .camp-person-row small { color: var(--muted); font-size: 12px; }
.camp-person-row button { flex: 0 0 auto; }

@media (max-width: 520px) {
  .camp-event-row { display: grid; grid-template-columns: minmax(0, 1fr); gap: 8px; }
  .camp-event-actions { justify-content: flex-start; }
  .camp-create-form { grid-template-columns: minmax(0, 1fr); }
  .camp-title-field { grid-column: auto; }
  .camp-link-row { align-items: flex-start; flex-direction: column; }
}
</style>
