import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"

const page = await readFile(new URL("../src/pages/SchoolLeavePage.vue", import.meta.url), "utf8")
const app = await readFile(new URL("../src/App.vue", import.meta.url), "utf8")
const team = await readFile(new URL("../src/pages/TeamPage.vue", import.meta.url), "utf8")
const memberDetail = await readFile(new URL("../src/pages/MemberDetailPage.vue", import.meta.url), "utf8")
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
assert.match(page, /function requestStatusLabel\(item: SchoolLeaveRequest\)/)
assert.match(page, /item\.status === "pending"[^]*?"待汇总"/)
assert.match(page, /item\.status === "withdrawn"[^]*?"已撤回"/)
assert.match(page, /item\.run_status === "sent"[^]*?"已发送"/)
assert.match(page, /return "已汇总"/)
assert.match(page, /requestStatusLabel\(item\)/)

// Member does not see admin management; admin gets a compact two-view switch defaulting to mine.
assert.match(page, /activeView = ref<"mine" \| "admin">\("mine"\)/)
assert.match(page, /<nav v-if="isAdmin" class="leave-view-tabs"/)
assert.match(page, />我的请假<\/button>/)
assert.match(page, />汇总管理<\/button>/)
assert.match(page, /<template v-if="activeView === 'mine' \|\| !isAdmin">/)
assert.match(page, /<template v-else-if="isAdmin">/)

// Submit fields remain one compact logical group.
assert.match(page, /<form class="leave-request-form"/)
assert.doesNotMatch(page, /management-form/)
assert.match(page, /class="leave-form-controls"[\s\S]*?leaveDate[\s\S]*?startTime[\s\S]*?endTime[\s\S]*?class="primary leave-submit"/)
assert.match(page, /\.leave-form-controls \{[^}]*grid-template-columns: minmax\(150px, 1\.1fr\) minmax\(250px, 1\.6fr\) auto/s)
assert.match(page, /\.leave-submit, \.leave-collect, \.leave-mark-sent \{ width: fit-content;/)
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

// Delivery is one run -> one DOCX. ZIP/send-message UI and clipboard logic are gone.
assert.match(page, /function runDocumentUrl\(runId: number\)/)
assert.match(page, /"\/api\/school-leave\/admin\/runs\/" \+ runId \+ "\/document"/)
assert.doesNotMatch(page, /zipUrl|documents\.zip|下载全部/)
assert.doesNotMatch(page, /发送文案|复制发送文案|navigator\.clipboard|send_message|copyMessage/)

// Ready runs are the first admin work section and expose one run-level download.
const adminTemplate = page.slice(page.indexOf('<template v-else-if="isAdmin">'))
assert.ok(adminTemplate.indexOf('class="leave-ready-section"') < adminTemplate.indexOf('class="leave-pending-section"'))
const readySection = page.slice(
  page.indexOf('<section v-if="readyRuns.length" class="leave-ready-section">'),
  page.indexOf('<section v-if="pendingAdminRequests.length" class="leave-pending-section">'),
)
assert.match(readySection, /run\.member_count \}\} 人 · \{\{ run\.groups\.length \}\} 个时间组/)
assert.match(readySection, />\s*下载请假材料\s*<\/button>/)
assert.equal((readySection.match(/runDocumentUrl\(run\.id\)/g) ?? []).length, 1)
assert.match(readySection, /class="leave-run-groups"/)
const readyGroups = readySection.slice(
  readySection.indexOf('<div class="leave-run-groups">'),
  readySection.indexOf('<footer class="leave-run-actions">'),
)
assert.match(readyGroups, /togglePreview\(run\.id, group\.index\)/)
assert.match(readyGroups, /名单/)
assert.doesNotMatch(readyGroups, /download\(|>下载</)
assert.match(page, /确认已经通过微信或 QQ 私聊老师发送了这些材料？/)
assert.match(readySection, /markSent\(run\)/)
assert.doesNotMatch(readySection, /deleteRun\(/)

// Reason edit and run cancellation remain ready-only overflow actions.
assert.match(readySection, /<details class="leave-more">/)
assert.match(readySection, /aria-label="更多管理操作"/)
assert.match(readySection, />修改统一事由<\/button>/)
assert.match(readySection, />取消本次汇总<\/button>/)
assert.match(readySection, /v-if="editingReasonRunId === run\.id" class="leave-reason-editor"/)
assert.match(readySection, /<textarea v-model="reasonDrafts\[run\.id\]"/)

// Sent history stays low-weight, can redownload one run DOCX, and has safe deletion.
assert.match(page, /sentRuns\.value\.slice\(0, 3\)/)
assert.match(page, /historyExpanded/)
assert.match(page, />发送历史<\/h2>/)
assert.match(page, /查看全部历史/)
assert.match(page, /class="leave-history-run"/)
assert.match(page, /run\.sent_by\?\.name/)
assert.match(page, /补充批次/)
const historySection = page.slice(page.indexOf('<section class="leave-history-section">'), page.indexOf("</template>\n</template>"))
assert.match(historySection, /run\.groups\.length \}\} 个时间组/)
assert.match(historySection, /leave-history-group/)
assert.doesNotMatch(historySection, /documentUrl\(run\.id, group\.index\)/)
assert.match(historySection, /runDocumentUrl\(run\.id\)/)
assert.match(historySection, />\s*下载请假材料\s*<\/button>/)
assert.match(historySection, /aria-label="更多历史操作"/)
assert.match(historySection, />\s*删除记录\s*<\/button>/)
assert.match(historySection, /deleteRun\(run, \$event\)/)
assert.doesNotMatch(page, /runs\.value\.filter\(\(item\) => item\.status === "cancelled"\)/)

// Delete confirmation states destructive scope, removes the confirmed record locally after DELETE succeeds, then reloads.
const deleteBody = page.match(/async function deleteRun\([^]*?\n}/)?.[0] ?? ""
assert.match(deleteBody, /删除这条发送记录？/)
assert.match(deleteBody, /run\.request_count/)
assert.match(deleteBody, /此操作不可恢复/)
assert.match(deleteBody, /api\.deleteSchoolLeaveRun\(run\.id\)/)
assert.match(deleteBody, /runs\.value = runs\.value\.filter\(\(item\) => item\.id !== run\.id\)/)
assert.match(deleteBody, /await load\(\)/)
assert.ok(
  deleteBody.indexOf("await api.deleteSchoolLeaveRun(run.id)") <
    deleteBody.indexOf("runs.value = runs.value.filter((item) => item.id !== run.id)") &&
    deleteBody.indexOf("runs.value = runs.value.filter((item) => item.id !== run.id)") <
      deleteBody.indexOf("await load()"),
)
assert.doesNotMatch(deleteBody, /activeView\.value\s*=/)
assert.doesNotMatch(deleteBody, /window\.location\.reload|scrollTo/)

// Empty management state stays compact.
const templateOnly = page.slice(page.indexOf("<template>"), page.indexOf("<style scoped>"))
assert.match(templateOnly, /当前没有需要处理的请假。/)
assert.match(templateOnly, /暂无记录/)
assert.doesNotMatch(templateOnly, /当前没有待汇总申请。/)
assert.doesNotMatch(templateOnly, /当前没有待发送批次。/)
assert.doesNotMatch(templateOnly, /暂无已发送批次。/)

// Reload after admin actions must preserve the selected admin view.
for (const functionName of ["collectNow", "saveReason", "cancelRun", "markSent", "deleteRun"]) {
  const body = page.match(new RegExp("async function " + functionName + "\\([^]*?\\n}"))?.[0] ?? ""
  assert.match(body, /await load\(\)/, functionName + " should reload School Leave data")
  assert.doesNotMatch(body, /activeView\.value\s*=/, functionName + " should preserve the current view")
}
assert.doesNotMatch(page, /window\.location\.reload/)

// 400px layout remains overflow-safe; run/history actions can wrap naturally.
assert.match(page, /@media \(max-width: 520px\)/)
assert.match(page, /\.leave-form-controls \{ grid-template-columns: minmax\(0, 1fr\); \}/)
assert.match(page, /\.leave-time-pair \{ grid-template-columns: minmax\(0, 1fr\) auto minmax\(0, 1fr\); \}/)
assert.match(page, /\.leave-run-download, \.leave-history-download \{ width: fit-content;/)
assert.match(page, /\.leave-history-actions \{ align-items: flex-start; \}/)
assert.match(page, /max-width: calc\(100vw - 32px\)/)
assert.match(page, /overflow-wrap: anywhere/)
assert.doesNotMatch(page, /min-width:\s*(?:4\d\d|[5-9]\d\d|\d{4,})px/)
assert.doesNotMatch(page, /width:\s*100vw/)

// Route, API, deletion and privacy contracts remain independent from Task data.
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
assert.match(api, /deleteSchoolLeaveRun/)
assert.match(api, /method: "DELETE"/)
assert.doesNotMatch(types, /send_message/)
assert.match(types, /run_status: SchoolLeaveRunStatus \| null/)
assert.doesNotMatch(types, /interface MemberSummary \{[^}]*student_id/s)

// School/team profile fields remain editable only through personal/admin member flows.
assert.match(app, /updateMeProfile/)
assert.doesNotMatch(team, /updateProfile/)
assert.match(memberDetail, /updateProfile/)
assert.match(api, /\/api\/auth\/me/)
assert.match(api, /\/api\/members\/\$\{memberId\}\/profile/)
assert.match(types, /student_id: string \| null/)
assert.match(types, /team_group: TeamGroup \| null/)

console.log("School Leave delivery and history controls frontend tests passed")
