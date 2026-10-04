import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"

const team = await readFile(new URL("../src/pages/TeamPage.vue", import.meta.url), "utf8")
const detail = await readFile(new URL("../src/pages/MemberDetailPage.vue", import.meta.url), "utf8")
const app = await readFile(new URL("../src/App.vue", import.meta.url), "utf8")
const api = await readFile(new URL("../src/api.ts", import.meta.url), "utf8")
const types = await readFile(new URL("../src/types.ts", import.meta.url), "utf8")

const memberList = team.slice(team.indexOf('<div class="member-list">'), team.lastIndexOf("</section>"))

// Team keeps one shared registration control and a browse-first member list.
assert.match(team, /<h2>团队注册</h2>/)
assert.match(team, /开启 72 小时注册/)
assert.match(team, /registrationWindow/)
assert.match(team, /registrationPath/)
assert.match(team, /复制注册链接/)
assert.match(team, /提前关闭/)
assert.doesNotMatch(team, /<h2>邀请成员</h2>/)
assert.doesNotMatch(team, /创建邀请/)
assert.doesNotMatch(team, /系统权限[sS]*?<select/)

assert.match(memberList, /member.name/)
assert.match(memberList, /member.email/)
assert.match(memberList, /groupLabel(member)/)
assert.match(memberList, /roleLabels[member.role]/)
assert.match(memberList, /memberStatusLabel(member)/)
assert.match(memberList, /学号 ${member.student_id}/)
assert.match(memberList, /学号未填写/)
assert.match(memberList, /emit('navigate', `/team/${member.id}`)/)
assert.doesNotMatch(memberList, /<input/)
assert.doesNotMatch(memberList, />停用</button>|>恢复</button>|生成邀请/)

// Member detail remains an admin-only route and edits only school/team profile fields.
assert.match(app, /const MemberDetailPage = defineAsyncComponent/)
assert.match(app, /const teamMemberDetailId = computed/)
assert.ok(app.includes('const match = path.value.match(/^\\/team\\/(\\d+)$/)'))
const detailLoader = app.slice(
  app.indexOf("else if (teamMemberDetailId.value !== null)"),
  app.indexOf('else if (routePath === "/team")'),
)
assert.match(detailLoader, /if (!isAdmin.value)[sS]*?navigate("/")/)
assert.match(detailLoader, /members.value = await api.members()/)

assert.match(detail, /<dt>姓名</dt>[sS]*?member.name/)
assert.match(detail, /<dt>邮箱</dt>[sS]*?member.email/)
assert.match(detail, /<dt>系统权限</dt>[sS]*?roleLabels[member.role]/)
assert.match(detail, /<dt>状态</dt>[sS]*?member.status/)
assert.match(detail, /v-model="studentIdDraft"/)
assert.match(detail, /v-model="teamGroupDraft"/)
assert.match(detail, /<span>所属组别</span>/)
assert.match(detail, /v-for="(label, code) in groupLabels"/)
assert.match(detail, /emit("updateProfile"/)
assert.match(app, /@update-profile="updateMemberProfile"/)
assert.match(api, /updateMemberProfile: (memberId: number, studentId: string | null, teamGroup: TeamGroup | null)/)
assert.match(api, //api/members/${memberId}/profile/)

// Existing invited accounts keep their legacy activation path only in member detail.
assert.match(detail, /member.status === 'invited'/)
assert.match(detail, /邀请尚未完成/)
assert.match(detail, /重新生成邀请/)
assert.match(detail, /复制邀请链接/)
assert.match(app, /@regenerate-invite="regenerateInvite"/)

// Role and task-member privacy are both reduced to the intended surface.
assert.match(types, /export type Role = "admin" | "member"/)
assert.doesNotMatch(types, /"manager"/)
assert.doesNotMatch(app, /isManager|任务管理员/)
assert.doesNotMatch(types, /interface MemberSummary {[^}]*(?:student_id|team_group)/s)
assert.match(types, /interface Member {[^}]*student_id: string | null[sS]*?team_group: TeamGroup | null/s)

// Fixed group labels are centralized in the app, not free-form member text.
for (const label of ["电控组", "机械组", "视觉组", "AI组", "运营组"]) {
  assert.ok(app.includes(label))
}

// Responsive member/profile layouts do not introduce a wide minimum viewport.
assert.match(team, /@media (max-width: 520px)/)
assert.match(team, /overflow-wrap: anywhere/)
assert.match(detail, /@media (max-width: 520px)/)
assert.match(detail, /grid-template-columns: minmax(78px, 96px) minmax(0, 1fr)/)
assert.match(detail, /@media (max-width: 720px)[sS]*?.member-profile-form/)
assert.doesNotMatch(team + detail, /width:s*100vw/)
assert.doesNotMatch(team + detail, /min-width:s*(?:4dd|[5-9]dd|d{4,})px/)

console.log("Team member detail and group profile frontend tests passed")
