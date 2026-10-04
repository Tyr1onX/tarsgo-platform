<script setup lang="ts">
import { ref, watch } from "vue"
import type { InviteResult, Member, Role } from "../types"

const props = defineProps<{
  members: Member[]
  latestInvite: InviteResult | null
  currentUserId: number | null
  roleLabels: Record<Role, string>
  formatDate: (value: string) => string
}>()

const emit = defineEmits<{
  invite: [payload: { name: string; email: string; role: Role }]
  regenerateInvite: [memberId: number]
  disableMember: [memberId: number]
  enableMember: [memberId: number]
  updateStudentId: [payload: { memberId: number; studentId: string }]
  copyInvite: []
  navigate: [path: string]
}>()

const memberName = ref("")
const memberEmail = ref("")
const memberRole = ref<Role>("member")
const studentIdDrafts = ref<Record<number, string>>({})

watch(
  () => props.members,
  (members) => {
    studentIdDrafts.value = Object.fromEntries(
      members.map((member) => [member.id, member.student_id ?? ""]),
    )
  },
  { immediate: true },
)

watch(() => props.latestInvite, (invite) => {
  if (!invite) return
  memberName.value = ""
  memberEmail.value = ""
  memberRole.value = "member"
})

function submitInvite() {
  emit("invite", { name: memberName.value, email: memberEmail.value, role: memberRole.value })
}
</script>

<template>
  <div class="page-title">
    <h1>团队</h1>
    <button type="button" @click="emit('navigate', '/knowledge')">团队资料</button>
  </div>
  <form class="management-form" @submit.prevent="submitInvite">
    <h2>邀请成员</h2>
    <label>
      姓名
      <input v-model="memberName" maxlength="100" required />
    </label>
    <label>
      邮箱
      <input v-model="memberEmail" type="email" maxlength="255" required />
    </label>
    <label>
      系统权限
      <select v-model="memberRole">
        <option value="member">成员</option>
        <option value="manager">任务管理员</option>
        <option value="admin">管理员</option>
      </select>
    </label>
    <button class="primary" type="submit">创建邀请</button>
  </form>

  <section v-if="latestInvite" class="invite-result">
    <div>
      <strong>{{ latestInvite.member.name }}</strong>
      <span>邀请有效至 {{ formatDate(latestInvite.expires_at) }}</span>
    </div>
    <button class="primary" type="button" @click="emit('copyInvite')">复制邀请链接</button>
  </section>

  <section>
    <div class="section-heading"><h2>成员</h2></div>
    <div class="member-list">
      <div v-for="member in members" :key="member.id" class="member-row">
        <div>
          <strong>{{ member.name }}</strong>
          <span>{{ member.email }}</span>
          <small>{{ roleLabels[member.role] }} · {{ member.status }}</small>
          <label class="member-student-id">
            学号
            <input
              v-model="studentIdDrafts[member.id]"
              maxlength="50"
              autocomplete="off"
              placeholder="未填写"
            />
            <button
              type="button"
              :disabled="(studentIdDrafts[member.id] ?? '').trim() === (member.student_id ?? '')"
              @click="emit('updateStudentId', { memberId: member.id, studentId: studentIdDrafts[member.id] ?? '' })"
            >保存</button>
          </label>
        </div>
        <div class="row-actions">
          <button v-if="member.status === 'invited'" type="button" @click="emit('regenerateInvite', member.id)">
            生成邀请
          </button>
          <button
            v-if="member.status === 'active' && member.id !== currentUserId"
            class="danger-text"
            type="button"
            @click="emit('disableMember', member.id)"
          >停用</button>
          <button v-if="member.status === 'disabled'" type="button" @click="emit('enableMember', member.id)">
            恢复
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.member-student-id {
  display: grid;
  grid-template-columns: auto minmax(110px, 160px) auto;
  align-items: center;
  gap: 8px;
  margin-top: 7px;
  color: var(--muted);
  font-size: 12px;
}

.member-student-id input {
  min-width: 0;
}

@media (max-width: 520px) {
  .member-student-id {
    grid-template-columns: auto minmax(0, 1fr) auto;
  }
}
</style>
