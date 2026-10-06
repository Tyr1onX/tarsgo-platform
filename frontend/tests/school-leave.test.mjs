import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"

const read = (path) => readFile(new URL(path, import.meta.url), "utf8")
const leavePage = await read("../src/pages/SchoolLeavePage.vue")
const dailyPage = await read("../src/pages/DailyLeavePage.vue")
const publicPage = await read("../src/pages/DailyLeavePublicPage.vue")
const legacyPage = await read("../src/pages/LegacySchoolLeaveHistory.vue")
const app = await read("../src/App.vue")
const api = await read("../src/api.ts")
const types = await read("../src/types.ts")

// The existing leave entry point now separates the two workflows.
assert.match(leavePage, /日常请假/)
assert.match(leavePage, /集中请假/)
assert.match(leavePage, /<DailyLeavePage/)
assert.match(leavePage, /<CampLeavePage/)

// Admin authorizes a fixed activity window; the member only downloads its own document.
for (const field of ["title", "start_at", "end_at", "open_until", "team_open", "public_enabled"]) {
  assert.match(dailyPage, new RegExp(`draft\\.value\\.${field}|v-model="draft\\.${field}"`))
}
assert.match(dailyPage, /createDailyLeaveWindow/)
assert.match(dailyPage, /downloadDailyLeaveDocument\(window\.id, offline\)/)
assert.match(dailyPage, /下载请假条/)
assert.match(dailyPage, /下载线下签章版/)
assert.match(dailyPage, /closeDailyLeaveWindow/)
assert.match(dailyPage, /<ConfirmDialog/)
assert.match(dailyPage, /当前开放窗口/)
assert.match(dailyPage, /profileReady/)
assert.match(dailyPage, /请先完善姓名、8 位学号、学院和队内身份/)
assert.doesNotMatch(dailyPage, /待汇总|补充汇总|等待其他成员|11:30 汇总/)
assert.doesNotMatch(dailyPage, /type="time"/)

// Public link shows immutable activity times and accepts only the three identity fields.
assert.match(publicPage, /publicDailyLeaveWindow\(props\.token\)/)
assert.match(publicPage, /generatePublicDailyLeaveDocument\(props\.token/)
assert.match(publicPage, /windowInfo\.start_at/)
assert.match(publicPage, /windowInfo\.end_at/)
assert.match(publicPage, /<CollegeSelect[\s\S]*required/)
assert.match(publicPage, /name,\s*student_id: studentId,\s*college: draft\.value\.college/s)
assert.match(publicPage, /windowInfo\.accepting_participants/)
assert.match(publicPage, /活动时间固定，不能修改/)
assert.doesNotMatch(publicPage, /start_at\s*[:=]|end_at\s*[:=]|participant_type|member_id|api\.(members|tasks|campLeaveAdmin)/)
assert.match(publicPage, /下载线下签章版/)
assert.match(api, /generatePublicDailyLeaveDocument: \(token: string, payload: DailyLeavePublicEntry/)
assert.match(api, /method: "POST", body: JSON\.stringify\(payload\)/)

// Public daily URL loads outside the authenticated application shell.
assert.match(app, /routePath\.startsWith\("\/leave\/daily\/"\)/)
assert.match(app, /path\.startsWith\('\/leave\/daily\/'\)/)
assert.match(app, /<DailyLeavePublicPage :token="dailyLeavePublicToken"/)

// Old aggregation data remains readable in a collapsed history section with original downloads.
assert.match(dailyPage, /legacyExpanded/)
assert.match(dailyPage, /<LegacySchoolLeaveHistory/)
assert.match(legacyPage, /schoolLeaveRuns\(\)/)
assert.match(legacyPage, /schoolLeaveRequests\(\)/)
assert.match(legacyPage, /downloadLegacySchoolLeaveRunDocument/)
assert.match(legacyPage, /downloadLegacySchoolLeaveGroupDocument/)
assert.match(legacyPage, /schoolLeaveResultUrl/)
assert.doesNotMatch(legacyPage, /createSchoolLeaveRequest|updateSchoolLeaveRequest|withdrawSchoolLeaveRequest|collectPendingSchoolLeave|uploadSchoolLeaveResult|deleteSchoolLeaveRun/)
assert.match(api, /schoolLeaveRequests/)
assert.match(api, /schoolLeaveRuns/)
assert.match(api, /deleteSchoolLeaveRun/)
assert.match(api, /\/api\/school-leave\/admin\/runs\/.*\/history-document/)
assert.match(types, /SchoolLeaveRunStatus = "ready" \| "awaiting_return" \| "completed" \| "cancelled"/)

// Old tables and routes are retained for existing history and file access.
assert.match(api, /\/api\/school-leave\/admin\/runs\/.*\/documents\//)
assert.match(api, /schoolLeaveResultUrl/)
assert.doesNotMatch(types, /interface MemberSummary \{[^}]*student_id/s)

// New UI remains narrow on mobile and avoids fixed-width page containers.
for (const page of [dailyPage, publicPage, legacyPage, leavePage]) {
  assert.doesNotMatch(page, /(?:^|[;{])\s*(?:min-width|width)\s*:\s*(?:4\d\d|[5-9]\d\d|\d{4,})px/)
  assert.doesNotMatch(page, /width:\s*100vw/)
}
assert.match(dailyPage, /@media \(max-width: 520px\)/)
assert.match(publicPage, /box-sizing: border-box; width: 100%; min-width: 0/)

console.log("Daily Leave V2 and legacy history frontend tests passed")
