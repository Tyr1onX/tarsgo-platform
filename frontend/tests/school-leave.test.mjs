import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"

const page = await readFile(new URL("../src/pages/SchoolLeavePage.vue", import.meta.url), "utf8")
const app = await readFile(new URL("../src/App.vue", import.meta.url), "utf8")
const api = await readFile(new URL("../src/api.ts", import.meta.url), "utf8")
const types = await readFile(new URL("../src/types.ts", import.meta.url), "utf8")
const style = await readFile(new URL("../src/style.css", import.meta.url), "utf8")

// Existing member request workflow remains intact.
assert.match(page, /createSchoolLeaveRequest/)
assert.match(page, /updateSchoolLeaveRequest/)
assert.match(page, /withdrawSchoolLeaveRequest/)
assert.match(page, /type="time" step="300"/)
assert.match(page, /相同请假时间会自动汇总到同一份请假材料中/)

// Member state copy follows the completion loop.
assert.match(page, /item\.status === "pending"[^]*?"待汇总"/)
assert.match(page, /item\.run_status === "awaiting_return"[^]*?"办理中"/)
assert.match(page, /item\.run_status === "completed" && item\.result_state === "cleared"[^]*?"已完成 · 材料已清理"/)
assert.match(page, /item\.run_status === "completed"[^]*?"已完成"/)
assert.doesNotMatch(page, /已发送|标记已发送|markSent/)
assert.doesNotMatch(api, /markSchoolLeaveRunSent|\/sent/)

// Ready is a single download action; successful fetch is followed by a data refresh.
assert.match(page, /<h2>待下载 <span>· \{\{ readyRuns\.length \}\}<\/span><\/h2>/)
assert.match(page, />\s*下载请假材料\s*<\/button>/)
assert.match(page, /async function downloadRunDocument\(run: SchoolLeaveRun\)/)
const downloadBody = page.match(/async function downloadRunDocument\([^]*?\n}/)?.[0] ?? ""
assert.match(downloadBody, /api\.downloadSchoolLeaveRunDocument\(run\.id\)/)
assert.match(downloadBody, /await load\(\)/)
assert.match(api, /downloadSchoolLeaveRunDocument/)
assert.match(api, /\/api\/school-leave\/admin\/runs\/.*\/document/)

// Awaiting-return UI is per exact group, with upload, view and replacement controls.
assert.match(page, /awaitingReturnRuns = computed\(\(\) => runs\.value\.filter\(\(item\) => item\.status === "awaiting_return"\)\)/)
assert.match(page, /<h2>待老师回传 <span>· \{\{ awaitingReturnRuns\.length \}\}/)
const awaitingSection = page.slice(
  page.indexOf('<section v-if="awaitingReturnRuns.length"'),
  page.indexOf('<section v-if="pendingAdminRequests.length"'),
)
assert.match(awaitingSection, /v-for="group in run\.groups"/)
assert.match(awaitingSection, /上传盖章结果/)
assert.match(awaitingSection, /重新上传/)
assert.match(awaitingSection, />\s*查看\s*<\/button>/)
assert.match(awaitingSection, /accept="\.jpg,\.jpeg,\.png,\.pdf,image\/jpeg,image\/png,application\/pdf"/)
assert.match(page, /api\.uploadSchoolLeaveResult\(run\.id, groupIndex, file\)/)
assert.match(api, /\/groups\/.*\/result/)
assert.match(api, /new FormData\(\)/)

// Completion is fully derived from result data; no manual completion control exists.
assert.match(page, /completedRuns = computed\(\(\) => runs\.value\.filter\(\(item\) => item\.status === "completed"\)\)/)
assert.match(page, /<h2>已完成<\/h2>/)
assert.doesNotMatch(page, /标记完成|completeSchoolLeave|finishSchoolLeave/)

// Completed history keeps original Word re-download and result replacement.
const historySection = page.slice(page.indexOf('<section class="leave-history-section">'), page.indexOf("</template>\n</template>"))
assert.match(historySection, /downloadRunDocument\(run\)/)
assert.match(historySection, /重新上传/)
assert.match(historySection, /openResult\(run\.id, group\.index\)/)
assert.match(historySection, /删除记录/)

// Member result access is shown only for completed + available result on that request.
assert.match(page, /item\.run_status === 'completed'/)
assert.match(page, /item\.result_state === 'available'/)
assert.match(page, /item\.run_id !== null/)
assert.match(page, /item\.group_index !== null/)
assert.match(page, />\s*下载盖章材料\s*<\/button>/)
assert.match(page, /api\.schoolLeaveResultUrl\(runId, groupIndex\)/)

// Lightweight admin todo count uses summary only, not all School Leave records in App.
assert.match(api, /schoolLeaveAdminSummary/)
assert.match(api, /\/api\/school-leave\/admin\/summary/)
assert.match(app, /const schoolLeaveTodoCount = ref\(0\)/)
assert.match(app, /api\.schoolLeaveAdminSummary\(\)/)
assert.match(app, /schoolLeaveTodoCount\.value = \(await api\.schoolLeaveAdminSummary\(\)\)\.todo_count/)
assert.match(app, /请假 <span v-if="isAdmin && schoolLeaveTodoCount" class="nav-count"/)
assert.match(app, /@todo-count="schoolLeaveTodoCount = \$event"/)
assert.match(style, /\.nav-count \{/)

// Types expose only the new state model and safe result metadata.
assert.match(types, /SchoolLeaveRunStatus = "ready" \| "awaiting_return" \| "completed" \| "cancelled"/)
assert.doesNotMatch(types, /SchoolLeaveRunStatus = [^\n]*"sent"/)
assert.match(types, /result_state: SchoolLeaveResultState \| null/)
assert.match(types, /group_index: number \| null/)
assert.match(types, /interface SchoolLeaveGroupResult/)
assert.match(types, /available: boolean/)
assert.doesNotMatch(types, /stored_path|stored_name/)

// UI stays compact and responsive; no generic todo/dashboard/notification system is introduced.
assert.match(page, /@media \(max-width: 520px\)/)
assert.match(page, /\.leave-form-controls \{ grid-template-columns: minmax\(0, 1fr\); \}/)
assert.match(page, /max-width: calc\(100vw - 32px\)/)
assert.doesNotMatch(page, /width:\s*100vw/)
assert.doesNotMatch(page, /min-width:\s*(?:4\d\d|[5-9]\d\d|\d{4,})px/)
assert.doesNotMatch(page + app, /通知中心|通用待办|Todo Center|dashboard/i)

// School Leave remains independent from task/profile permission models.
assert.match(app, /path === '\/leave'/)
assert.match(app, /<SchoolLeavePage/)
assert.match(api, /schoolLeaveRequests/)
assert.match(api, /schoolLeaveRuns/)
assert.match(api, /deleteSchoolLeaveRun/)
assert.doesNotMatch(types, /interface MemberSummary \{[^}]*student_id/s)

console.log("School Leave completion-loop frontend tests passed")
