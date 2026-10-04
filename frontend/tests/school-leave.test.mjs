import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"

const page = await readFile(new URL("../src/pages/SchoolLeavePage.vue", import.meta.url), "utf8")
const app = await readFile(new URL("../src/App.vue", import.meta.url), "utf8")
const team = await readFile(new URL("../src/pages/TeamPage.vue", import.meta.url), "utf8")
const api = await readFile(new URL("../src/api.ts", import.meta.url), "utf8")
const types = await readFile(new URL("../src/types.ts", import.meta.url), "utf8")

// Member submit/edit/withdraw workflow.
assert.match(page, /请假日期/)
assert.match(page, /type="time" step="300"/)
assert.match(page, /createSchoolLeaveRequest/)
assert.match(page, /updateSchoolLeaveRequest/)
assert.match(page, /withdrawSchoolLeaveRequest/)
assert.match(page, /相同请假时间会自动汇总到同一份请假材料中，请按自己的实际缺课时间填写。/)
assert.match(page, /请先完善学号，生成学校请假材料时需要使用。/)

// Admin exact grouping, downloads, copy, cancel and sent confirmation.
assert.match(page, /run\.groups\.length/)
assert.match(page, /group\.count/)
assert.match(page, /documents\/\$\{group\.index\}/)
assert.match(page, /documents\.zip/)
assert.match(page, /navigator\.clipboard\.writeText\(run\.send_message\)/)
assert.match(page, /确认已经通过微信或 QQ 私聊老师发送了这些材料？/)
assert.match(page, /cancelSchoolLeaveRun/)
assert.match(page, /LEAVE_CONTACT_PHONE 未配置/)

// Mobile-first layout: time/reason/actions collapse without fixed content widths.
assert.match(page, /@media \(max-width: 520px\)/)
assert.match(page, /\.leave-time-grid \{\s*grid-template-columns: 1fr;/s)
assert.match(page, /\.leave-reason \{\s*grid-template-columns: 1fr;/s)
assert.doesNotMatch(page, /min-width:\s*(?:4\d\d|[5-9]\d\d|\d{4,})px/)

// Route and navigation stay independent from Task.
assert.match(app, /path === '\/leave'/)
assert.match(app, />\s*请假\s*<\/button>/)
assert.match(app, /<SchoolLeavePage/)
assert.doesNotMatch(types, /interface MemberSummary \{[^}]*student_id/s)

// Student id is editable only through personal/admin member flows in the frontend.
assert.match(app, /updateMeStudentId/)
assert.match(team, /updateStudentId/)
assert.match(api, /\/api\/auth\/me/)
assert.match(api, /\/api\/members\/\$\{memberId\}\/student-id/)
assert.match(types, /student_id: string \| null/)

console.log("School leave frontend tests passed")
