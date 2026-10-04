import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"

const page = await readFile(new URL("../src/pages/SchoolLeavePage.vue", import.meta.url), "utf8")
const app = await readFile(new URL("../src/App.vue", import.meta.url), "utf8")
const team = await readFile(new URL("../src/pages/TeamPage.vue", import.meta.url), "utf8")
const api = await readFile(new URL("../src/api.ts", import.meta.url), "utf8")
const types = await readFile(new URL("../src/types.ts", import.meta.url), "utf8")

// Member submit/edit/withdraw workflow remains intact.
assert.match(page, /请假日期/)
assert.match(page, /type="time" step="300"/)
assert.match(page, /createSchoolLeaveRequest/)
assert.match(page, /updateSchoolLeaveRequest/)
assert.match(page, /withdrawSchoolLeaveRequest/)
assert.match(page, /相同请假时间会自动汇总到同一份请假材料中，请按自己的实际缺课时间填写。/)
assert.match(page, /请先完善学号，生成学校请假材料时需要使用。/)
assert.match(page, /暂无请假申请/)
assert.match(page, /requestStatusLabel/)

// Member does not see admin management; admin gets a compact two-view switch defaulting to mine.
assert.match(page, /activeView = ref<"mine" \| "admin">\("mine"\)/)
assert.match(page, /<nav v-if="isAdmin" class="leave-view-tabs"/)
assert.match(page, />我的请假<\/button>/)
assert.match(page, />汇总管理<\/button>/)
assert.match(page, /<template v-if="activeView === 'mine' \|\| !isAdmin">/)
assert.match(page, /<template v-else-if="isAdmin">/)

// Submit fields are one compact logical group and no longer reuse management-form.
assert.match(page, /<form class="leave-request-form"/)
assert.doesNotMatch(page, /management-form/)
assert.match(page, /class="leave-form-controls"[\s\S]*?leaveDate[\s\S]*?startTime[\s\S]*?endTime[\s\S]*?class="primary leave-submit"/)
assert.match(page, /\.leave-form-controls \{[^}]*grid-template-columns: minmax\(150px, 1\.1fr\) minmax\(250px, 1\.6fr\) auto/s)
assert.match(page, /\.leave-submit, \.leave-collect, \.leave-mark-sent \{ width: fit-content;/)
assert.doesNotMatch(page, /\.leave-submit[^}]*width:\s*100%/s)
assert.match(page, /class="leave-inline-notice"/)

// Pending preview groups only exact start_at + end_at and expands names on demand.
assert.match(page, /const exactKey = request\.start_at \+ "\\u0000" \+ request\.end_at/)
assert.match(page, /pendingPreviewDays = computed/)
assert.match(page, /pendingMemberCount/)
assert.match(page, /formatTimeSpan\(group\.startAt, group\.endAt\)/)
assert.match(page, /request\.member_name_snapshot/)
assert.match(page, /request\.student_id_snapshot/)
assert.match(page, /togglePendingPreview\(group\.key\)/)
assert.doesNotMatch(page, /fuzzy|overlap|mergeRange|expandRange/i)

// Ready runs are the first admin work section and retain all operational actions.
const adminTemplate = page.slice(page.indexOf('<template v-else-if="isAdmin">'))
assert.ok(adminTemplate.indexOf('class="leave-ready-section"') < adminTemplate.indexOf('class="leave-pending-section"'))
assert.match(page, /run\.groups\.length \}\} 份材料/)
assert.match(page, /group\.count/)
assert.match(page, /documentUrl\(run\.id, group\.index\)/)
assert.match(page, /zipUrl\(run\.id\)/)
assert.match(page, /navigator\.clipboard\.writeText\(run\.send_message\)/)
assert.match(page, /确认已经通过微信或 QQ 私聊老师发送了这些材料？/)
assert.match(page, /markSchoolLeaveRunSent/)
assert.match(page, /cancelSchoolLeaveRun/)
assert.match(page, /class="primary leave-mark-sent"/)

// Reason edit and run cancellation are low-frequency overflow actions.
assert.match(page, /<details class="leave-more">/)
assert.match(page, /aria-label="更多管理操作"/)
assert.match(page, />修改统一事由<\/button>/)
assert.match(page, />取消本次汇总<\/button>/)
assert.match(page, /v-if="editingReasonRunId === run\.id" class="leave-reason-editor"/)
assert.match(page, /<textarea v-model="reasonDrafts\[run\.id\]"/)
assert.doesNotMatch(page, /<div class="leave-reason">[\s\S]*?<textarea/s)

// Sent runs are low-weight history: three by default, expandable, and still downloadable.
assert.match(page, /sentRuns\.value\.slice\(0, 3\)/)
assert.match(page, /historyExpanded/)
assert.match(page, />发送历史<\/h2>/)
assert.match(page, /查看全部历史/)
assert.match(page, /class="leave-history-run"/)
assert.match(page, /run\.sent_by\?\.name/)
assert.match(page, /补充批次/)
assert.match(page, /leave-history-group[\s\S]*?documentUrl\(run\.id, group\.index\)/)
assert.doesNotMatch(page, /runs\.value\.filter\(\(item\) => item\.status === "cancelled"\)/)

// Empty management state is compact instead of rendering separate zero-state sections.
const templateOnly = page.slice(page.indexOf("<template>"), page.indexOf("<style scoped>"))
assert.match(templateOnly, /当前没有需要处理的请假。/)
assert.match(templateOnly, /暂无记录/)
assert.doesNotMatch(templateOnly, /当前没有待汇总申请。/)
assert.doesNotMatch(templateOnly, /当前没有待发送批次。/)
assert.doesNotMatch(templateOnly, /暂无已发送批次。/)

// Reload after admin actions must preserve the selected admin view.
for (const functionName of ["collectNow", "saveReason", "cancelRun", "markSent"]) {
  const body = page.match(new RegExp("async function " + functionName + "\\([^]*?\\n}"))?.[0] ?? ""
  assert.match(body, /await load\(\)/, functionName + " should reload School Leave data")
  assert.doesNotMatch(body, /activeView\.value\s*=/, functionName + " should preserve the current view")
}
assert.doesNotMatch(page, /window\.location\.reload/)

// 400px layout: form collapses, time relation stays compact, overflow menu stays inside viewport.
assert.match(page, /@media \(max-width: 520px\)/)
assert.match(page, /\.leave-form-controls \{ grid-template-columns: minmax\(0, 1fr\); \}/)
assert.match(page, /\.leave-time-pair \{ grid-template-columns: minmax\(0, 1fr\) auto minmax\(0, 1fr\); \}/)
assert.match(page, /max-width: calc\(100vw - 32px\)/)
assert.match(page, /overflow-wrap: anywhere/)
assert.doesNotMatch(page, /min-width:\s*(?:4\d\d|[5-9]\d\d|\d{4,})px/)
assert.doesNotMatch(page, /width:\s*100vw/)

// Route, API, download and privacy contracts remain independent from Task data.
assert.match(app, /path === '\/leave'/)
assert.match(app, />\s*请假\s*<\/button>/)
assert.match(app, /<SchoolLeavePage/)
assert.match(api, /schoolLeaveRequests/)
assert.match(api, /schoolLeaveAdminRequests/)
assert.match(api, /schoolLeaveRuns/)
assert.match(api, /collectSchoolLeave/)
assert.match(api, /updateSchoolLeaveRunReason/)
assert.match(api, /cancelSchoolLeaveRun/)
assert.match(api, /markSchoolLeaveRunSent/)
assert.doesNotMatch(types, /interface MemberSummary \{[^}]*student_id/s)

// Student id remains editable only through personal/admin member flows.
assert.match(app, /updateMeStudentId/)
assert.match(team, /updateStudentId/)
assert.match(api, /\/api\/auth\/me/)
assert.match(api, /\/api\/members\/\$\{memberId\}\/student-id/)
assert.match(types, /student_id: string \| null/)

console.log("School Leave UX v1.1 frontend tests passed")
