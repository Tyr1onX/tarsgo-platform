<script setup lang="ts">
import { computed, ref } from "vue"
import MemberSearchFilters from "../components/MemberSearchFilters.vue"
import { filterMembers } from "../memberSearch.js"
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

const memberSearchQuery = ref("")
const memberGroupFilter = ref("")
const filteredMembers = computed(() =>
  filterMembers(
    props.members,
    memberSearchQuery.value,
    memberGroupFilter.value,
    ["name", "email", "student_id"],
  ),
)
const enabledMembers = computed(() => filteredMembers.value.filter((member) => member.status !== "disabled"))
const allDisabledMembers = computed(() => props.members.filter((member) => member.status === "disabled"))
const disabledMembers = computed(() => filteredMembers.value.filter((member) => member.status === "disabled"))

function memberStatusLabel(member: Member) {
  if (member.status === "invited") return "邀请中"
  if (member.status === "disabled") return "已停用"
  return "正常"
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
      <span>{{ enabledMembers.length }}</span>
    </div>
    <MemberSearchFilters
      v-model:query="memberSearchQuery"
      v-model:group="memberGroupFilter"
      :group-labels="groupLabels"
      search-label="搜索姓名、邮箱或学号"
      search-placeholder="输入姓名、邮箱或学号"
    />
    <div class="member-list">
      <div v-for="member in enabledMembers" :key="member.id" class="member-row team-member-row">
        <button class="team-member-link" type="button" @click="emit('navigate', `/team/${member.id}`)">
          <span class="team-member-summary">
            <strong>{{ member.name }}</strong>
            <span>{{ member.email }}</span>
            <small>{{ groupLabel(member) }} · {{ roleLabels[member.role] }} · {{ memberStatusLabel(member) }}</small>
            <span class="team-member-student-id">
              {{ member.student_id ? `学号 ${member.student_id}` : "学号未填写" }}
            </span>
          </span>
          <span class="team-member-chevron" aria-hidden="true">›</span>
        </button>
      </div>
      <p v-if="!enabledMembers.length" class="team-member-empty">当前筛选条件下没有匹配的成员。</p>
    </div>

    <details v-if="allDisabledMembers.length" class="team-disabled-members">
      <summary>已停用成员（{{ allDisabledMembers.length }}）</summary>
      <div class="member-list">
        <div v-for="member in disabledMembers" :key="member.id" class="member-row team-member-row">
          <button class="team-member-link" type="button" @click="emit('navigate', `/team/${member.id}`)">
            <span class="team-member-summary">
              <strong>{{ member.name }}</strong>
              <span>{{ member.email }}</span>
              <small>{{ groupLabel(member) }} · {{ roleLabels[member.role] }} · {{ memberStatusLabel(member) }}</small>
              <span class="team-member-student-id">
                {{ member.student_id ? `学号 ${member.student_id}` : "学号未填写" }}
              </span>
            </span>
            <span class="team-member-chevron" aria-hidden="true">›</span>
          </button>
        </div>
        <p v-if="!disabledMembers.length" class="team-member-empty">当前筛选条件下没有匹配的已停用成员。</p>
      </div>
    </details>
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
  display: block;
  padding: 0;
}

.team-member-empty {
  margin: 0;
  padding: 12px 0;
  color: var(--muted);
  font-size: 13px;
}

.team-member-link {
  width: 100%;
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 16px;
  border: 0;
  border-radius: 0;
  background: transparent;
  padding: 15px 0;
  color: inherit;
  text-align: left;
}

.team-member-link:hover {
  background: var(--hover);
}

.team-member-link:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.team-member-summary {
  min-width: 0;
  display: grid;
  gap: 2px;
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

.team-member-chevron {
  color: var(--faint);
  font-size: 18px;
}

.team-disabled-members {
  margin-top: 14px;
}

.team-disabled-members > summary {
  width: fit-content;
  padding: 4px 0;
  color: var(--muted);
  cursor: pointer;
}

.team-disabled-members[open] > summary {
  margin-bottom: 8px;
}

@media (max-width: 520px) {
  .team-registration-action {
    width: 100%;
  }

  .team-member-link {
    gap: 10px;
    padding: 14px 0;
  }
}
</style>
