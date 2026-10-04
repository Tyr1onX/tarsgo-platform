<script setup lang="ts">
import { computed, ref, watch } from "vue"
import type { InviteResult, Member, Role, TeamGroup } from "../types"

const props = defineProps<{
  member: Member
  currentUserId: number | null
  latestInvite: InviteResult | null
  roleLabels: Record<Role, string>
  groupLabels: Record<TeamGroup, string>
  formatDate: (value: string) => string
  profileSaving: boolean
}>()

const emit = defineEmits<{
  regenerateInvite: [memberId: number]
  disableMember: [memberId: number]
  enableMember: [memberId: number]
  updateProfile: [payload: { memberId: number; studentId: string; teamGroup: TeamGroup | null }]
  copyInvite: []
  navigate: [path: string]
}>()

const studentIdDraft = ref("")
const teamGroupDraft = ref<TeamGroup | "">("")

watch(
  () => props.member,
  (member) => {
    studentIdDraft.value = member.student_id ?? ""
    teamGroupDraft.value = member.team_group ?? ""
  },
  { immediate: true },
)

const normalizedStudentId = computed(() => studentIdDraft.value.trim())
const savedStudentId = computed(() => props.member.student_id ?? "")
const profileChanged = computed(
  () =>
    normalizedStudentId.value !== savedStudentId.value ||
    teamGroupDraft.value !== (props.member.team_group ?? ""),
)
const currentInvite = computed(() =>
  props.latestInvite?.member.id === props.member.id ? props.latestInvite : null,
)

function memberStatusLabel(member: Member) {
  if (member.status === "invited") return "邀请中"
  if (member.status === "disabled") return "已停用"
  return "正常"
}

function saveProfile() {
  if (!profileChanged.value || props.profileSaving) return
  emit("updateProfile", {
    memberId: props.member.id,
    studentId: studentIdDraft.value,
    teamGroup: teamGroupDraft.value || null,
  })
}
</script>

<template>
  <button class="member-detail-back" type="button" @click="emit('navigate', '/team')">← 返回团队</button>

  <header class="member-detail-heading">
    <h1>{{ member.name }}</h1>
    <span>成员资料</span>
  </header>

  <section class="member-detail-section">
    <h2>基本信息</h2>
    <dl class="member-detail-fields">
      <div>
        <dt>姓名</dt>
        <dd>{{ member.name }}</dd>
      </div>
      <div>
        <dt>邮箱</dt>
        <dd>{{ member.email }}</dd>
      </div>
      <div>
        <dt>系统权限</dt>
        <dd>{{ roleLabels[member.role] }}</dd>
      </div>
      <div>
        <dt>状态</dt>
        <dd>{{ memberStatusLabel(member) }}</dd>
      </div>
    </dl>
  </section>

  <section class="member-detail-section">
    <h2>学校 / 团队资料</h2>
    <form class="member-profile-form" @submit.prevent="saveProfile">
      <label>
        <span>学号</span>
        <input
          v-model="studentIdDraft"
          maxlength="50"
          autocomplete="off"
          placeholder="未填写学号"
        />
      </label>
      <label>
        <span>所属组别</span>
        <select v-model="teamGroupDraft">
          <option value="">未填写</option>
          <option v-for="(label, code) in groupLabels" :key="code" :value="code">{{ label }}</option>
        </select>
      </label>
      <button
        class="primary member-profile-save"
        type="submit"
        :disabled="!profileChanged || profileSaving"
      >
        {{ profileSaving ? "保存中…" : "保存修改" }}
      </button>
    </form>
  </section>

  <section class="member-detail-section member-account-section">
    <h2>账号操作</h2>

    <template v-if="member.status === 'invited'">
      <p class="member-account-note">邀请尚未完成</p>
      <button type="button" class="member-secondary-action" @click="emit('regenerateInvite', member.id)">
        重新生成邀请
      </button>

      <div v-if="currentInvite" class="member-invite-result">
        <span>邀请有效至 {{ formatDate(currentInvite.expires_at) }}</span>
        <button type="button" @click="emit('copyInvite')">复制邀请链接</button>
      </div>
    </template>

    <button
      v-else-if="member.status === 'active' && member.id !== currentUserId"
      class="member-danger-action"
      type="button"
      @click="emit('disableMember', member.id)"
    >
      停用成员
    </button>

    <p v-else-if="member.status === 'active'" class="member-account-note">
      当前登录账号不能停用自己。
    </p>

    <button
      v-else-if="member.status === 'disabled'"
      class="member-secondary-action"
      type="button"
      @click="emit('enableMember', member.id)"
    >
      恢复成员
    </button>
  </section>
</template>

<style scoped>
.member-detail-back {
  border: 0;
  background: transparent;
  padding: 3px 0;
  color: var(--muted);
}

.member-detail-back:hover {
  color: var(--text);
}

.member-detail-heading {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin: 10px 0 28px;
}

.member-detail-heading h1 {
  margin: 0;
}

.member-detail-heading span {
  color: var(--faint);
  font-size: 13px;
}

.member-detail-section {
  padding: 20px 0 24px;
  border-top: 1px solid var(--line);
}

.member-detail-section h2 {
  margin: 0 0 14px;
  font-size: 14px;
}

.member-detail-fields {
  margin: 0;
}

.member-detail-fields > div {
  display: grid;
  grid-template-columns: minmax(100px, 150px) minmax(0, 1fr);
  gap: 16px;
  padding: 8px 0;
}

.member-detail-fields dt {
  color: var(--muted);
  font-size: 12.5px;
}

.member-detail-fields dd {
  min-width: 0;
  margin: 0;
  overflow-wrap: anywhere;
}

.member-profile-form {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto;
  align-items: end;
  gap: 10px;
  max-width: 720px;
}

.member-profile-form label {
  min-width: 0;
  display: grid;
  gap: 6px;
  color: var(--muted);
  font-size: 12.5px;
}

.member-profile-form input,
.member-profile-form select {
  min-width: 0;
}

.member-profile-save {
  width: fit-content;
  white-space: nowrap;
}

.member-account-section {
  display: grid;
  justify-items: start;
  gap: 9px;
}

.member-account-section h2 {
  margin-bottom: 5px;
}

.member-account-note {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
}

.member-danger-action,
.member-secondary-action,
.member-invite-result button {
  border: 0;
  background: transparent;
  padding: 4px 0;
}

.member-danger-action {
  color: var(--danger);
}

.member-secondary-action,
.member-invite-result button {
  color: var(--secondary);
}

.member-invite-result {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px 14px;
  margin-top: 3px;
  color: var(--muted);
  font-size: 12.5px;
}

.member-detail-heading,
.member-detail-fields,
.member-profile-form,
.member-invite-result {
  min-width: 0;
}

@media (max-width: 720px) {
  .member-profile-form {
    grid-template-columns: minmax(0, 1fr);
  }

  .member-profile-save {
    justify-self: start;
  }
}

@media (max-width: 520px) {
  .member-detail-heading {
    align-items: flex-start;
    flex-direction: column;
    gap: 3px;
    margin-bottom: 22px;
  }

  .member-detail-fields > div {
    grid-template-columns: minmax(78px, 96px) minmax(0, 1fr);
    gap: 10px;
  }
}
</style>
