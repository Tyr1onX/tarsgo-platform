import assert from "node:assert/strict"
import { readFileSync } from "node:fs"

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8")
const page = read("../src/pages/CampLeavePage.vue")
const publicPage = read("../src/pages/CampLeavePublicPage.vue")
const leavePage = read("../src/pages/SchoolLeavePage.vue")
const app = read("../src/App.vue")
const api = read("../src/api.ts")
const types = read("../src/types.ts")

assert.match(leavePage, /日常请假/)
assert.match(leavePage, /集中请假/)
assert.match(leavePage, /activeSection === 'camp'/)
assert.match(leavePage, /<CampLeavePage/)

// Members only see their own participation state, and the member document route derives college server-side.
assert.match(api, /campLeaveEvents: \(\) => request<CampLeaveEventMember\[]>\("\/api\/camp-leave\/events"\)/)
assert.match(types, /interface CampLeaveEventMember \{[^}]*joined: boolean[^}]*participant_type: CampLeaveParticipantType \| null/s)
assert.doesNotMatch(types.match(/interface CampLeaveEventMember \{[^}]*\}/s)?.[0] ?? "", /(?:^|\n)\s*(?:participant_count|public_path|participants):/)
assert.match(page, /event\.joined \? "取消参加" : "确认参加"/)
assert.match(page, /profileReady/)
assert.doesNotMatch(page.match(/const profileReady = computed\(\(\) =>[\s\S]*?\n\)/)?.[0] ?? "", /team_membership/)
assert.doesNotMatch(page, /队内身份/)
assert.match(page, /emit\('navigate', '\/me'\)/)
assert.match(api, /downloadCampLeaveMemberDocument: \(eventId: number\)/)
assert.match(api, /\/api\/camp-leave\/events\/\$\{eventId\}\/document/)
assert.doesNotMatch(api.match(/downloadCampLeaveMemberDocument:[^\n]*/)?.[0] ?? "", /college/)

// Admin downloads one college at a time; the signed version is primary, offline version is in the menu.
assert.match(page, /camp-college-group/)
assert.match(page, /group\.college_name/)
assert.match(page, /group\.count/)
assert.match(page, /downloadCampLeaveAdminCollegeDocument/)
assert.match(page, /下載集中请假|下载 DOCX/)
assert.match(page, /下载线下签章版/)
assert.match(page, /group\.college/)
assert.match(api, /downloadCampLeaveAdminCollegeDocument: \(eventId: number, college: string, offline = false\)/)
assert.match(api, /\/colleges\/\$\{encodeURIComponent\(college\)\}\/document\$\{offline \? "\?offline=true" : ""\}/)
assert.doesNotMatch(page + api, /\.zip|application\/zip|ZIP/)

// Public collection contains no roster or internal event calls.
assert.match(publicPage, /api\.publicCampLeaveEvent\(props\.token\)/)
assert.match(publicPage, /api\.colleges\(\)/)
assert.match(publicPage, /<CollegeSelect[\s\S]*?:options="colleges"[\s\S]*?required/)
assert.match(publicPage, /name,\s*student_id: studentId,\s*college: draft\.value\.college/s)
assert.doesNotMatch(publicPage, /api\.(members|campLeaveEvents|campLeaveAdminEvents|tasks)\(/)
assert.doesNotMatch(publicPage, /participant_type|member_id|团队成员|任务列表/)
assert.match(app, /routePath\.startsWith\("\/leave\/camp\/"\)/)
assert.match(app, /routePath\.startsWith\("\/leave\/daily\/"\)/)

// The CampLeaveEvent snapshot data model still distinguishes type from team group.
assert.match(types, /export type CampLeaveType = "winter" \| "summer"/)
assert.match(types, /export type CampLeaveParticipantType = "formal" \| "reserve" \| "other"/)
assert.match(api, /publicJoinCampLeaveEvent: \(token: string, payload: \{ name: string; student_id: string; college: string \}\)/)

// 400px mobile width uses a single column and shrinkable content.
assert.match(page, /@media \(max-width: 520px\)/)
assert.match(page, /grid-template-columns: minmax\(0, 1fr\)/)
assert.match(page, /\.camp-leave-page \{ min-width: 0; max-width: 100%; \}/)
assert.match(page, /overflow-wrap: anywhere/)
assert.doesNotMatch(page + publicPage, /(?:^|[;{])\s*(?:min-width|width)\s*:\s*(?:4\d\d|[5-9]\d\d|\d{4,})px/)
assert.match(publicPage, /box-sizing: border-box; width: 100%; min-width: 0/)

console.log("Camp Leave college document frontend tests passed")
