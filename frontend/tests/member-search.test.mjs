import assert from "node:assert/strict"
import { readFileSync } from "node:fs"

import { filterMembers, UNASSIGNED_TEAM_GROUP } from "../src/memberSearch.js"

const app = readFileSync(new URL("../src/App.vue", import.meta.url), "utf8")
const teamPage = readFileSync(new URL("../src/pages/TeamPage.vue", import.meta.url), "utf8")
const filtersComponent = readFileSync(new URL("../src/components/MemberSearchFilters.vue", import.meta.url), "utf8")

const members = [
  { id: 1, name: "李明", email: "liming@example.com", student_id: "26000001", team_group: "electrical" },
  { id: 2, name: "王华", email: "wanghua@example.com", student_id: "26000002", team_group: "operations" },
  { id: 3, name: "Ava Chen", email: "ava@example.com", student_id: "26000003", team_group: null },
]

assert.deepEqual(filterMembers(members, " 李 ").map((member) => member.id), [1])
assert.deepEqual(filterMembers(members, "", "operations").map((member) => member.id), [2])
assert.deepEqual(filterMembers(members, "王", "operations").map((member) => member.id), [2])
assert.deepEqual(
  filterMembers(members, "26000003", "", ["name", "email", "student_id"]).map((member) => member.id),
  [3],
)
assert.deepEqual(
  filterMembers(members, "AVA@EXAMPLE.COM", UNASSIGNED_TEAM_GROUP, ["name", "email"]).map((member) => member.id),
  [3],
)
assert.deepEqual(
  filterMembers(members, "example.com", "electrical", ["name", "email", "student_id"]).map((member) => member.id),
  [1],
)
const inactiveCurrentOwner = { id: 4, name: "旧负责人", team_group: null }
const ownerOptions = [...members, inactiveCurrentOwner]
const activeMemberIds = new Set(members.map((member) => member.id))
const filterOwnerOptions = (query, group) =>
  filterMembers(ownerOptions, query, group)
    .filter((member) => !group || activeMemberIds.has(member.id))
assert.deepEqual(
  filterOwnerOptions("旧", "").map((member) => member.id),
  [4],
)
assert.deepEqual(filterOwnerOptions("", UNASSIGNED_TEAM_GROUP).map((member) => member.id), [3])
assert.deepEqual(filterOwnerOptions("李", "electrical").map((member) => member.id), [1])

assert.match(app, /MemberSearchFilters/)
assert.match(app, /v-model="taskOwnerId"[\s\S]*?type="radio"/)
assert.match(app, /v-model="taskCollaboratorIds" type="checkbox"/)
assert.match(app, /v-for="member in filteredCollaborators"[\s\S]*?v-model="taskCollaboratorIds"/)
assert.match(app, /taskCollaboratorIds\.length/)
assert.match(app, /filterMembers\(activeMembers\.value, taskCollaboratorSearch/)
const collaboratorFilterSource = app.match(/const filteredCollaborators = computed\(\(\) =>([\s\S]*?)\n\)/)?.[1]
assert.ok(collaboratorFilterSource)
assert.doesNotMatch(collaboratorFilterSource, /taskCollaboratorIds/)
assert.match(app, /taskOwnerId\.value/)
assert.match(app, /computed<TaskAssigneeOption\[]>\(\(\) => \{[\s\S]*?options\.unshift\(\{ \.\.\.owner, team_group: null \}\)/)
assert.match(app, /\.filter\(\(member\) => !taskOwnerGroupFilter\.value \|\| activeMemberIds\.value\.has\(member\.id\)\)/)
assert.match(app, /ownerOptions\.value\.find\(\(member\) => member\.id === taskOwnerId\.value\)/)
assert.match(teamPage, /filterMembers\([\s\S]*?props\.members,[\s\S]*?memberSearchQuery\.value,[\s\S]*?memberGroupFilter\.value,[\s\S]*?\["name", "email", "student_id"\]/)
assert.match(teamPage, /MemberSearchFilters/)
assert.match(filtersComponent, /type="search"/)
assert.match(filtersComponent, /全部组别/)
assert.match(filtersComponent, /组别未填写/)
assert.match(filtersComponent, /@media \(max-width: 560px\)/)

console.log("Member search, group filtering, combined criteria, and persistent task selections passed")
