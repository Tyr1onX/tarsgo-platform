import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"

const app = await readFile(new URL("../src/App.vue", import.meta.url), "utf8")
const css = await readFile(new URL("../src/style.css", import.meta.url), "utf8")
const api = await readFile(new URL("../src/api.ts", import.meta.url), "utf8")
const team = await readFile(new URL("../src/pages/TeamPage.vue", import.meta.url), "utf8")
const memberDetail = await readFile(new URL("../src/pages/MemberDetailPage.vue", import.meta.url), "utf8")

const meStart = app.indexOf(`<template v-else-if="path === '/me'">`)
const meEditStart = app.indexOf(`<template v-else-if="path === '/me/edit'">`)
const leaveStart = app.indexOf(`<template v-else-if="path === '/leave'">`)
assert.ok(meStart >= 0 && meEditStart > meStart && leaveStart > meEditStart)

const me = app.slice(meStart, meEditStart)
const meEdit = app.slice(meEditStart, leaveStart)

// /me stays read-only and shows school/team identity fields.
assert.ok(me.includes("<h1>我的</h1>"))
assert.ok(me.includes("user?.name"))
assert.ok(me.includes("user?.email"))
assert.ok(me.includes("roleLabels[user.role]"))
assert.ok(me.includes('user?.student_id || "学号未填写"'))
assert.ok(me.includes("所属组别"))
assert.ok(me.includes("groupLabels[user.team_group]"))
assert.ok(me.includes("collegeOptions.find((college) => college.code === user?.college)"))
assert.ok(me.includes("membershipLabels[user.team_membership]"))
assert.ok(me.includes("navigate('/me/edit')"))
assert.doesNotMatch(me, /studentIdDraft|teamGroupDraft|<input|<select|保存修改/)
assert.ok(me.includes('@click="logout"'))

// /me/edit is the single personal editing surface and uses fixed groups.
assert.ok(meEdit.includes("← 返回我的"))
assert.ok(meEdit.includes("<h1>编辑资料</h1>"))
assert.ok(meEdit.includes("<h2>学校信息</h2>"))
assert.ok(meEdit.includes('v-model="studentIdDraft"'))
assert.ok(meEdit.includes('v-model="teamGroupDraft"'))
assert.ok(meEdit.includes('v-for="(label, code) in groupLabels"'))
assert.ok(meEdit.includes('v-model="collegeDraft"'))
assert.doesNotMatch(meEdit, /队内身份|teamMembershipDraft|team_membership/)
assert.ok(meEdit.includes(':disabled="profileSaving || !myProfileChanged"'))
assert.ok(meEdit.includes("保存修改"))

// PATCH updates both fields through the single existing profile endpoint.
assert.ok(app.includes("const myProfileChanged = computed"))
assert.ok(app.includes('teamGroupDraft.value !== (user.value?.team_group ?? "")'))
const saveStart = app.indexOf("async function saveMyProfile()")
const saveEnd = app.indexOf("\n}", saveStart)
const saveBody = saveStart >= 0 && saveEnd > saveStart ? app.slice(saveStart, saveEnd + 2) : ""
assert.ok(saveBody.includes("!myProfileChanged.value"))
assert.ok(saveBody.includes("api.updateMeProfile"))
assert.ok(saveBody.includes("studentIdDraft.value.trim() || null"))
assert.ok(saveBody.includes("teamGroupDraft.value || null"))
assert.ok(saveBody.includes("collegeDraft.value || null"))
assert.doesNotMatch(saveBody, /teamMembershipDraft|team_membership/)
assert.ok(saveBody.includes('navigate("/me")'))
assert.ok(api.includes("updateMeProfile: (payload: MyProfilePayload)"))
assert.ok(!api.includes("updateMeStudentId"))

// "我的" remains active for overview and edit routes.
assert.equal((app.match(/:class="\{ active: isMeRoute \}"/g) ?? []).length, 2)

// Compact actions and responsive layouts remain bounded.
assert.doesNotMatch(css, /\.full\s*\{[^}]*width:\s*100%/s)
assert.doesNotMatch(app, /class="[^"]*\bfull\b/)
assert.match(css, /\.profile-logout\s*\{[^}]*width:\s*fit-content/s)
assert.match(css, /\.profile-save,\s*\.member-profile-save\s*\{[^}]*width:\s*fit-content/s)
assert.ok(memberDetail.includes('class="member-profile-form"'))
assert.match(css, /\.profile-student-edit-form,\s*\.member-profile-form\s*\{[^}]*display:\s*grid/s)
assert.match(css, /\.profile-student-edit-form input,[\s\S]*?\.member-profile-form \.college-select__input\s*\{[^}]*height:\s*40px/s)
assert.match(css, /\.profile-save,\s*\.member-profile-save\s*\{[^}]*height:\s*34px/s)
assert.match(css, /\.profile-save:disabled,\s*\.member-profile-save:disabled\s*\{[^}]*background:\s*var\(--surface\)/s)
assert.match(css, /@media \(max-width: 1000px\)[\s\S]*?\.profile-student-edit-form\s*\{[^}]*grid-template-columns:\s*minmax\(0, 1fr\)/s)
assert.match(css, /@media \(max-width: 1000px\)[\s\S]*?\.member-profile-form\s*\{[^}]*grid-template-columns:\s*minmax\(0, 1fr\)/s)
assert.ok(team.includes('class="primary team-registration-action"'))
assert.doesNotMatch(app, /taskFormOpen|class="management-form task-form"/)
assert.match(css, /\.auth-form\s*\{[^}]*width:\s*min\(100%, 380px\)/s)
assert.doesNotMatch(
  css.match(/\.profile-field-row[\s\S]*?\.management-form/)?.[0] ?? "",
  /width:\s*100vw|min-width:\s*(?:4\d\d|[5-9]\d\d|\d{4,})px/,
)

console.log("My profile group editing and action width tests passed")
