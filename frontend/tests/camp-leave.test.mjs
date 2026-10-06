import assert from "node:assert/strict"
import { readFileSync } from "node:fs"

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8")
const page = read("../src/pages/CampLeavePage.vue")
const publicPage = read("../src/pages/CampLeavePublicPage.vue")
const leavePage = read("../src/pages/SchoolLeavePage.vue")
const app = read("../src/App.vue")
const api = read("../src/api.ts")
const types = read("../src/types.ts")
const packageJson = read("../package.json")

assert.match(leavePage, /日常请假/)
assert.match(leavePage, /集中请假/)
assert.match(leavePage, /activeSection === 'camp'/)
assert.match(leavePage, /<CampLeavePage/)
assert.match(leavePage, /schoolLeaveRequests\(\)/)
assert.match(leavePage, /downloadRunDocument\(run\)/)

// Member lists expose only each event and the signed-in member's own state.
assert.match(api, /campLeaveEvents: \(\) => request<CampLeaveEventMember\[]>\("\/api\/camp-leave\/events"\)/)
assert.match(types, /interface CampLeaveEventMember \{[^}]*joined: boolean[^}]*participant_type: CampLeaveParticipantType \| null/s)
assert.doesNotMatch(types.match(/interface CampLeaveEventMember \{[^}]*\}/s)?.[0] ?? "", /(?:^|\n)\s*(?:participant_count|public_path|participants):/)
assert.match(page, /event\.joined \? "取消参加" : "确认参加"/)
assert.match(page, /event\.accepting_participants/)
assert.match(page, /profileReady/)
assert.match(page, /emit\('navigate', '\/me'\)/)

// Admin list detail is grouped only by college, with immutable snapshot labels.
assert.match(api, /campLeaveAdminEvent: \(eventId: number\)/)
assert.match(page, /camp-college-group/)
assert.match(page, /group\.college_name/)
assert.match(page, /group\.count/)
assert.match(page, /identityLabel\(person\.participant_type\)/)
assert.match(page, /api\.removeCampLeaveParticipant/)
assert.match(page, /api\.closeCampLeaveEvent/)
assert.match(page, /确认参加|取消参加/)

// Public registration has no authenticated team-data calls and submits only the three requested fields.
assert.match(publicPage, /api\.publicCampLeaveEvent\(props\.token\)/)
assert.match(publicPage, /api\.colleges\(\)/)
assert.match(publicPage, /<CollegeSelect[\s\S]*?:options="colleges"[\s\S]*?required/)
assert.match(publicPage, /name,\s*student_id: studentId,\s*college: draft\.value\.college/s)
assert.doesNotMatch(publicPage, /api\.(members|campLeaveEvents|campLeaveAdminEvents|tasks)\(/)
assert.doesNotMatch(publicPage, /participant_type|member_id|团队成员|任务列表/)
assert.match(app, /routePath\.startsWith\("\/leave\/camp\/"\)/)
assert.match(app, /if \(routePath\.startsWith\("\/leave\/camp\/"\)\) \{\s*\/\/ Public camp signup page intentionally loads no authenticated team data\./)
assert.match(app, /path\.startsWith\('\/leave\/camp\/'\)/)
assert.match(api, /publicJoinCampLeaveEvent: \(token: string, payload: \{ name: string; student_id: string; college: string \}\)/)

// 400px mobile width uses one-column flows and shrinkable content rather than fixed-width cards.
assert.match(page, /@media \(max-width: 520px\)/)
assert.match(page, /grid-template-columns: minmax\(0, 1fr\)/)
assert.match(page, /\.camp-leave-page \{ min-width: 0; max-width: 100%; \}/)
assert.match(page, /overflow-wrap: anywhere/)
assert.doesNotMatch(page + publicPage, /(?:^|[;{])\s*(?:min-width|width)\s*:\s*(?:4\d\d|[5-9]\d\d|\d{4,})px/)
assert.match(publicPage, /box-sizing: border-box; width: 100%; min-width: 0/)
assert.match(packageJson, /camp-leave\.test\.mjs/)

console.log("Camp Leave V1 frontend tests passed")
