<script setup lang="ts">
import type { Member, Role, TeamGroup, TeamRegistrationWindow } from "../types"

const props = defineProps<{
  members: Member[]
  registrationWindow: TeamRegistrationWindow | null
  registrationPath: string
  openingRegistration: boolean
  closingRegistration: boolean
  roleLabels: Record<Role, string>
  groupLabels: Record<TeamGroup, string>
  formatDate: (value: string) => string
}>()

const emit = defineEmits<{
  openRegistration: []
  closeRegistration: []
  copyRegistration: []
  navigate: [path: string]
}>()

function memberStatusLabel(member: Member) {
  return member.status === "invited" ? "邀请中" : member.status
}

function groupLabel(member: Member) {
  return member.team_group ? props.groupLabels[member.team_group] : "组别未填写"
}
</script>

<template>
  <div class="page-title">
    <h1>团队</h1>
    <button type="button" @click="emit('navigate', '/knowledge')">团队资料</button>
  </div>

  <section class="team-registration">
    <div class="section-heading">
      <h2>团队注册</h2>
    </div>

    <template v-if="!registrationWindow">
      <p class="team-registration-copy">团队注册当前未开放。</p>
      <button
        class="primary team-registration-action"
        type="button"
        :disabled="openingRegistration"
        @click="emit('openRegistration')"
      >
        {{ openingRegistration ? "正在开启…" : "开启 72 小时注册" }}
      </button>
    </template>

    <template v-else>
      <div class="team-registration-status">
        <span>开放至</span>
        <strong>{{ formatDate(registrationWindow.expires_at) }}</strong>
      </div>

      <template v-if="registrationPath">
        <p class="team-registration-copy">注册链接已生成。</p>
        <button class="primary team-registration-action" type="button" @click="emit('copyRegistration')">
          复制注册链接
        </button>
      </template>
      <p v-else class="team-registration-copy">
        注册链接已出于安全原因不再保存。如需新的链接，请关闭后重新开启。
      </p>

      <button
        class="team-registration-close"
        type="button"
        :disabled="closingRegistration"
        @click="emit('closeRegistration')"
      >
        {{ closingRegistration ? "正在关闭…" : "提前关闭" }}
      </button>
    </template>
  </section>

  <section>
    <div class="section-heading">
      <h2>成员</h2>
      <span>{{ members.length }}</span>
    </div>
    <div class="member-list">
      <div v-for="member in members" :key="member.id" class="member-row team-member-row">
        <div class="team-member-summary">
          <strong>{{ member.name }}</strong>
          <span>{{ member.email }}</span>
          <small>{{ groupLabel(member) }} · {{ roleLabels[member.role] }} · {{ memberStatusLabel(member) }}</small>
          <span class="team-member-student-id">
            {{ member.student_id ? `学号 ${member.student_id}` : "学号未填写" }}
          </span>
        </div>
        <div class="row-actions team-member-action">
          <button type="button" @click="emit('navigate', `/team/${member.id}`)">编辑</button>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.team-registration {
  padding: 0 0 28px;
  margin-bottom: 28px;
  border-bottom: 1px solid var(--line);
}

.team-registration-copy {
  max-width: 620px;
  margin: 8px 0 14px;
  color: var(--muted);
  overflow-wrap: anywhere;
}

.team-registration-status {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
  margin: 8px 0;
  color: var(--muted);
}

.team-registration-status strong {
  color: var(--text);
}

.team-registration-action,
.team-registration-close {
  width: fit-content;
}

.team-registration-close {
  display: block;
  margin-top: 10px;
  border: 0;
  padding: 4px 0;
  background: transparent;
  color: var(--secondary);
}

.team-member-row {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
}

.team-member-summary {
  min-width: 0;
}

.team-member-summary strong,
.team-member-summary span,
.team-member-summary small {
  overflow-wrap: anywhere;
}

.team-member-student-id {
  margin-top: 5px;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.5;
}

.team-member-action {
  align-self: center;
}

@media (max-width: 520px) {
  .team-registration-action {
    width: 100%;
  }

  .team-member-row {
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
  }

  .team-member-action {
    justify-content: flex-end;
  }
}
</style>
