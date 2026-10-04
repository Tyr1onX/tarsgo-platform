import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"

const app = await readFile(new URL("../src/App.vue", import.meta.url), "utf8")
const css = await readFile(new URL("../src/style.css", import.meta.url), "utf8")
const api = await readFile(new URL("../src/api.ts", import.meta.url), "utf8")
const team = await readFile(new URL("../src/pages/TeamPage.vue", import.meta.url), "utf8")

const meStart = app.indexOf('<template v-else-if="path === '/me'">')
const meEditStart = app.indexOf('<template v-else-if="path === '/me/edit'">')
const leaveStart = app.indexOf('<template v-else-if="path === '/leave'">')
assert.ok(meStart >= 0 && meEditStart > meStart && leaveStart > meEditStart)

const me = app.slice(meStart, meEditStart)
const meEdit = app.slice(meEditStart, leaveStart)

// /me stays read-only and shows both school/team profile fields.
assert.match(me, /<h1>我的</h1>/)
assert.match(me, /user?.name/)
assert.match(me, /user?.email/)
assert.match(me, /roleLabels[user.role]/)
assert.match(me, /user?.student_id || "学号未填写"/)
assert.match(me, /所属组别/)
assert.match(me, /groupLabels[user.team_group]/)
assert.match(me, /navigate('/me/edit')/)
assert.doesNotMatch(me, /studentIdDraft|teamGroupDraft|<input|<select|保存修改/)
assert.match(me, /@click="logout"/)

// /me/edit is the single personal editing surface and uses fixed groups.
assert.match(meEdit, /← 返回我的/)
assert.match(meEdit, /<h1>编辑资料</h1>/)
assert.match(meEdit, /<h2>学校信息</h2>/)
assert.match(meEdit, /v-model="studentIdDraft"/)
assert.match(meEdit, /v-model="teamGroupDraft"/)
assert.match(meEdit, /v-for="(label, code) in groupLabels"/)
assert.match(meEdit, /:disabled="profileSaving || !myProfileChanged"/)
assert.match(meEdit, /保存修改/)

// PATCH updates both fields without adding another profile endpoint.
assert.match(app, /const myProfileChanged = computed/)
assert.match(app, /teamGroupDraft.value !== (user.value?.team_group ?? "")/)
const saveBody = app.match(/async function saveMyProfile()[sS]*?
}/)?.[0] ?? ""
assert.match(saveBody, /!myProfileChanged.value/)
assert.match(saveBody, /api.updateMeProfile/)
assert.match(saveBody, /studentIdDraft.value.trim() || null/)
assert.match(saveBody, /teamGroupDraft.value || null/)
assert.match(saveBody, /navigate("/me")/)
assert.match(api, /updateMeProfile: (studentId: string | null, teamGroup: TeamGroup | null)/)
assert.doesNotMatch(api, /updateMeStudentId/)

// "我的" remains active for overview and edit routes.
assert.equal((app.match(/:class="{ active: isMeRoute }"/g) ?? []).length, 2)

// Compact actions and responsive layouts remain bounded.
assert.doesNotMatch(css, /.fulls*{[^}]*width:s*100%/s)
assert.doesNotMatch(app, /class="[^"]*full/)
assert.match(css, /.profile-logouts*{[^}]*width:s*fit-content/s)
assert.match(css, /.profile-saves*{[^}]*width:s*fit-content/s)
assert.match(css, /@media (max-width: 520px)[sS]*?.profile-student-edit-forms*{[^}]*flex-direction:s*column/s)
assert.match(team, /class="primary team-registration-action"/)
assert.match(app, /<form v-if="isAdmin && taskFormOpen" class="management-form task-form"[sS]*?<button class="primary" type="submit">/)
assert.match(css, /.auth-forms*{[^}]*width:s*min(100%, 380px)/s)
assert.doesNotMatch(css.match(/.profile-field-row[sS]*?.management-form/)?.[0] ?? "", /width:s*100vw|min-width:s*(?:4dd|[5-9]dd|d{4,})px/)

console.log("My profile group editing and action width tests passed")
