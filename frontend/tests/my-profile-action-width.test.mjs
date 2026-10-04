import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"

const app = await readFile(new URL("../src/App.vue", import.meta.url), "utf8")
const css = await readFile(new URL("../src/style.css", import.meta.url), "utf8")
const api = await readFile(new URL("../src/api.ts", import.meta.url), "utf8")
const team = await readFile(new URL("../src/pages/TeamPage.vue", import.meta.url), "utf8")

const meStart = app.indexOf('<template v-else-if="path === \'/me\'">')
const meEditStart = app.indexOf('<template v-else-if="path === \'/me/edit\'">')
const leaveStart = app.indexOf('<template v-else-if="path === \'/leave\'">')
assert.ok(meStart >= 0 && meEditStart > meStart && leaveStart > meEditStart)

const me = app.slice(meStart, meEditStart)
const meEdit = app.slice(meEditStart, leaveStart)

// /me is a read-only overview.
assert.match(me, /<h1>我的<\/h1>/)
assert.match(me, /user\?\.name/)
assert.match(me, /user\?\.email/)
assert.match(me, /roleLabels\[user\.role\]/)
assert.match(me, /user\?\.student_id \|\| "学号未填写"/)
assert.match(me, /navigate\('\/me\/edit'\)/)
assert.match(me, />编辑 ><\/button>/)
assert.doesNotMatch(me, /studentIdDraft/)
assert.doesNotMatch(me, /<input/)
assert.doesNotMatch(me, /保存修改|>保存</)
assert.match(me, /class="secondary profile-logout"/)
assert.doesNotMatch(me, /class="[^"]*full/)
assert.match(me, /@click="logout"/)

// /me/edit is the only personal student-id editing surface.
assert.match(meEdit, /← 返回我的/)
assert.match(meEdit, /<h1>编辑资料<\/h1>/)
assert.match(meEdit, /<h2>学校信息<\/h2>/)
assert.match(meEdit, /v-model="studentIdDraft"/)
assert.match(meEdit, /placeholder="未填写学号"/)
assert.match(meEdit, /:disabled="studentIdSaving \|\| !myStudentIdChanged"/)
assert.match(meEdit, /保存修改/)

// Route setup and save behavior reuse the existing API and update local user state.
assert.match(app, /const isMeRoute = computed\(\(\) => path\.value === "\/me" \|\| path\.value === "\/me\/edit"\)/)
assert.match(app, /const myStudentIdChanged = computed/)
assert.match(app, /else if \(routePath === "\/me\/edit"\)[\s\S]*?studentIdDraft\.value = user\.value\?\.student_id \?\? ""/)
assert.match(app, /else if \(routePath === "\/me"\)[\s\S]*?Profile overview is intentionally read-only/)
const saveBody = app.match(/async function saveMyStudentId\(\)[\s\S]*?\n}/)?.[0] ?? ""
assert.match(saveBody, /!myStudentIdChanged\.value/)
assert.match(saveBody, /api\.updateMeStudentId\(studentIdDraft\.value\.trim\(\) \|\| null\)/)
assert.match(saveBody, /user\.value = await api\.updateMeStudentId/)
assert.match(saveBody, /navigate\("\/me"\)/)
assert.doesNotMatch(saveBody, /window\.location\.reload/)
assert.match(api, /updateMeStudentId: \(studentId: string \| null\)/)

// "我的" stays active throughout the overview/edit route pair.
assert.equal((app.match(/:class="\{ active: isMeRoute \}"/g) ?? []).length, 2)

// The old full-width utility was only profile debt and is gone.
assert.doesNotMatch(css, /\.full\s*\{[^}]*width:\s*100%/s)
assert.doesNotMatch(app, /class="[^"]*\bfull\b/)

// Profile actions stay compact and mobile layouts do not force horizontal overflow.
assert.match(css, /\.profile-logout\s*\{[^}]*width:\s*fit-content/s)
assert.match(css, /\.profile-save\s*\{[^}]*width:\s*fit-content/s)
assert.match(css, /\.profile-field-row\s*\{[^}]*grid-template-columns:\s*minmax\(70px, 110px\) minmax\(0, 1fr\) auto/s)
assert.match(css, /@media \(max-width: 520px\)[\s\S]*?\.profile-student-edit-form\s*\{[^}]*flex-direction:\s*column/s)
assert.doesNotMatch(css.match(/\.profile-field-row[\s\S]*?\.management-form/)?.[0] ?? "", /width:\s*100vw|min-width:\s*(?:4\d\d|[5-9]\d\d|\d{4,})px/)

// Action-width audit: only the clearly stretched management actions are compacted.
assert.match(css, /\.management-form > \.primary,[\s\S]*?\.invite-result > \.primary\s*\{[^}]*justify-self:\s*start[^}]*width:\s*fit-content/s)
assert.match(team, /<button class="primary" type="submit">创建邀请<\/button>/)
assert.match(app, /<form v-if="isManager && taskFormOpen" class="management-form task-form"[\s\S]*?<button class="primary" type="submit">/)
assert.match(css, /\.auth-form\s*\{[^}]*width:\s*min\(100%, 380px\)/s)
assert.match(css, /\.planner-generate\s*\{\s*width:\s*100%;\s*min-height:\s*46px;\s*\}/)

console.log("My profile detail UX and action width audit tests passed")
