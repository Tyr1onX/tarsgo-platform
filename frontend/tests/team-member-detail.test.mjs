import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"

const team = await readFile(new URL("../src/pages/TeamPage.vue", import.meta.url), "utf8")
const detail = await readFile(new URL("../src/pages/MemberDetailPage.vue", import.meta.url), "utf8")
const app = await readFile(new URL("../src/App.vue", import.meta.url), "utf8")
const api = await readFile(new URL("../src/api.ts", import.meta.url), "utf8")
const types = await readFile(new URL("../src/types.ts", import.meta.url), "utf8")

const memberList = team.slice(team.indexOf('<div class="member-list">'), team.lastIndexOf("</section>"))

// Team is now a browse-only member list.
assert.match(memberList, /member\.name/)
assert.match(memberList, /member\.email/)
assert.match(memberList, /roleLabels\[member\.role\]/)
assert.match(memberList, /memberStatusLabel\(member\)/)
assert.match(memberList, /学号 \$\{member\.student_id\}/)
assert.match(memberList, /学号未填写/)
assert.match(memberList, /emit\('navigate', `\/team\/\$\{member\.id\}`\)/)
assert.match(memberList, />编辑<\/button>/)
assert.doesNotMatch(memberList, /<input/)
assert.doesNotMatch(memberList, />保存<\/button>/)
assert.doesNotMatch(memberList, />停用<\/button>/)
assert.doesNotMatch(memberList, />恢复<\/button>/)
assert.doesNotMatch(memberList, /生成邀请/)
assert.match(team, /member\.status === "invited" \? "邀请中" : member\.status/)

// Member detail is its own admin route and survives direct loads by reusing the admin-only member list API.
assert.match(app, /const MemberDetailPage = defineAsyncComponent/)
assert.match(app, /const teamMemberDetailId = computed/)
assert.ok(app.includes('const match = path.value.match(/^\\/team\\/(\\d+)$/)'))
assert.match(app, /else if \(teamMemberDetailId\.value !== null\)/)
const detailLoader = app.slice(
  app.indexOf("else if (teamMemberDetailId.value !== null)"),
  app.indexOf('else if (routePath === "/team")'),
)
assert.match(detailLoader, /if \(!isAdmin\.value\)[\s\S]*?navigate\("\/"\)/)
assert.match(detailLoader, /members\.value = await api\.members\(\)/)
assert.match(detailLoader, /routeNotFound\.value = true/)
assert.match(app, /teamMemberDetailId !== null && teamMemberDetail/)
assert.match(app, /<MemberDetailPage/)
assert.match(app, /:class="\{ active: isTeamRoute \}"/)
assert.doesNotMatch(app, /window\.location\.reload/)

// Basic member data is read-only; student_id is the focused editable field.
assert.match(detail, /<h1>\{\{ member\.name \}\}<\/h1>/)
assert.match(detail, /<dt>姓名<\/dt>[\s\S]*?member\.name/)
assert.match(detail, /<dt>邮箱<\/dt>[\s\S]*?member\.email/)
assert.match(detail, /<dt>系统权限<\/dt>[\s\S]*?roleLabels\[member\.role\]/)
assert.match(detail, /<dt>状态<\/dt>[\s\S]*?member\.status/)
assert.match(detail, /v-model="studentIdDraft"/)
assert.match(detail, /props\.member\.student_id \?\? ""/)
assert.match(detail, /placeholder="未填写学号"/)
assert.match(detail, /:disabled="!studentIdChanged \|\| studentIdSaving"/)
assert.match(detail, /emit\("updateStudentId", \{ memberId: props\.member\.id, studentId: studentIdDraft\.value \}\)/)
assert.match(app, /replaceMemberInState\(await api\.updateMemberStudentId/)
assert.match(app, /notice\.value = "学号已更新"/)
assert.match(api, /updateMemberStudentId: \(memberId: number, studentId: string \| null\)/)

// Account actions only live in detail and preserve protection/confirmation semantics.
assert.match(detail, /member\.status === 'active' && member\.id !== currentUserId/)
assert.match(detail, />\s*停用成员\s*<\/button>/)
assert.match(detail, /member\.status === 'disabled'/)
assert.match(detail, />\s*恢复成员\s*<\/button>/)
assert.match(detail, /当前登录账号不能停用自己/)
assert.match(app, /停用后该成员会立即退出登录，确定停用？/)
assert.doesNotMatch(team, /disableMember|enableMember/)

// Invited members keep invite regeneration in detail, while the list only labels them as pending.
assert.match(detail, /member\.status === 'invited'/)
assert.match(detail, /邀请尚未完成/)
assert.match(detail, />\s*重新生成邀请\s*<\/button>/)
assert.match(detail, /currentInvite/)
assert.match(detail, /复制邀请链接/)
assert.match(app, /@regenerate-invite="regenerateInvite"/)

// Student-id privacy remains unchanged for Task member summaries.
assert.doesNotMatch(types, /interface MemberSummary \{[^}]*student_id/s)
assert.match(types, /interface Member \{[^}]*student_id: string \| null/s)
assert.match(api, /members: \(\) => request<Member\[]>\("\/api\/members"\)/)

// Compact responsive layout: no forced viewport width and mobile fields/actions can wrap.
assert.match(team, /@media \(max-width: 520px\)/)
assert.match(team, /grid-template-columns: minmax\(0, 1fr\) auto/)
assert.match(team, /overflow-wrap: anywhere/)
assert.match(detail, /@media \(max-width: 520px\)/)
assert.match(detail, /grid-template-columns: minmax\(78px, 96px\) minmax\(0, 1fr\)/)
assert.match(detail, /\.member-student-form \{[\s\S]*?flex-direction: column/)
assert.match(detail, /\.member-student-save \{[\s\S]*?width: fit-content/)
assert.doesNotMatch(team + detail, /width:\s*100vw/)
assert.doesNotMatch(team + detail, /min-width:\s*(?:4\d\d|[5-9]\d\d|\d{4,})px/)

console.log("Team member detail UX frontend tests passed")
