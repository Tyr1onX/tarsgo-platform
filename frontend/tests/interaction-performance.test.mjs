import assert from "node:assert/strict"
import { readFileSync } from "node:fs"

import {
  claimableTask,
  compareTaskDeadlines,
  deriveRootStatus,
  mergeRecentActivities,
  patchTaskCollection,
  prependUniqueActivity,
  setPendingTaskAction,
  taskMatchesView,
} from "../src/taskState.js"

const app = readFileSync(new URL("../src/App.vue", import.meta.url), "utf8")
const api = readFileSync(new URL("../src/api.ts", import.meta.url), "utf8")
const knowledgePage = readFileSync(new URL("../src/pages/KnowledgePage.vue", import.meta.url), "utf8")
const teamPage = readFileSync(new URL("../src/pages/TeamPage.vue", import.meta.url), "utf8")

const member = { id: 7 }
const owner = { id: 8 }
const root = { id: 1, parent_id: null, deadline: "2026-10-10", status: "todo" }
const unclaimed = {
  id: 2, parent_id: 1, deadline: "2026-10-11", owner: null,
  owner_claimable: true, status: "todo", collaborators: [],
}
const assigned = {
  id: 3, parent_id: 1, deadline: "2026-10-12", owner,
  owner_claimable: false, status: "todo", collaborators: [],
}

assert.equal(taskMatchesView(unclaimed, "claimable", member.id), true)
assert.equal(taskMatchesView(unclaimed, "mine", member.id), false)
assert.equal(taskMatchesView(assigned, "all", member.id), true)
assert.equal(claimableTask(unclaimed), true)
assert.equal(claimableTask({ ...unclaimed, status: "done" }), false)

const afterClaim = { ...unclaimed, owner: member }
assert.deepEqual(patchTaskCollection([unclaimed], afterClaim, "claimable", member.id), [])
assert.deepEqual(patchTaskCollection([], afterClaim, "mine", member.id).map((task) => task.id), [2])
const afterUnclaim = { ...afterClaim, owner: null }
assert.deepEqual(patchTaskCollection([afterClaim], afterUnclaim, "mine", member.id), [])
assert.deepEqual(patchTaskCollection([], afterUnclaim, "claimable", member.id).map((task) => task.id), [2])

const joined = { ...assigned, collaborators: [member] }
assert.equal(taskMatchesView(joined, "mine", member.id), true)
assert.deepEqual(patchTaskCollection([assigned], joined, "mine", member.id).map((task) => task.id), [3])
const left = { ...joined, collaborators: [] }
assert.deepEqual(patchTaskCollection([joined], left, "mine", member.id), [])

assert.equal(deriveRootStatus([{ status: "todo" }, { status: "todo" }]), "todo")
assert.equal(deriveRootStatus([{ status: "done" }, { status: "done" }]), "done")
assert.equal(deriveRootStatus([{ status: "doing" }, { status: "todo" }]), "doing")
assert.deepEqual(
  patchTaskCollection([root, unclaimed, assigned], { ...unclaimed, status: "doing" }, "all", member.id, true)
    .find((task) => task.id === root.id).status,
  "doing",
)

const pending = setPendingTaskAction(new Map(), 2, "join")
assert.equal(pending.get(2), "join")
assert.equal(pending.has(3), false)
assert.equal(setPendingTaskAction(pending, 2, null).has(2), false)

const deadlineOrdered = [
  { id: 8, deadline: null },
  { id: 3, deadline: "2026-10-11T12:00:00" },
  { id: 2, deadline: "2026-10-10T12:00:00" },
  { id: 7, deadline: null },
  { id: 4, deadline: "2026-10-11T12:00:00" },
]
assert.deepEqual(deadlineOrdered.sort(compareTaskDeadlines).map((task) => task.id), [2, 3, 4, 7, 8])

const older = { id: 4, content: "older" }
const latest = { id: 5, content: "latest" }
assert.deepEqual(prependUniqueActivity([older], latest).map((activity) => activity.id), [5, 4])
assert.deepEqual(mergeRecentActivities([older], [latest, older]).map((activity) => activity.id), [5, 4])

for (const action of ["updateOwnTaskStatus", "claimTask", "unclaimTask", "joinTask", "leaveTask"]) {
  const body = app.match(new RegExp(`async function ${action}\\([\\s\\S]*?\\n}\\n`))?.[0]
  assert.ok(body, `${action} handler exists`)
  assert.doesNotMatch(body, /loadRoute\s*\(/, `${action} does not reload the route`)
  assert.match(body, /runTaskAction/, `${action} has task-local pending state`)
}
assert.match(app, /function replaceTaskInState\(updated: Task\)/)
assert.doesNotMatch(app.match(/async function startNewTask\([\s\S]*?\n}/)?.[0] ?? "", /parent\.deadline/)
assert.match(app, /deadline: task\.deadline \|\| null/)
assert.match(app, /截止时间（可选）[\s\S]*?没有明确时间可以留空。/)
assert.match(app, /v-if="task\.deadline" class="planner-summary-deadline"/)
assert.match(app, /v-if="detailTask\.deadline"/)
const assigneeLoader = app.match(/async function ensureTaskAssignees\([\s\S]*?\n}/)?.[0]
assert.ok(assigneeLoader)
assert.match(assigneeLoader, /api\.taskAssignees\(\)/)
assert.doesNotMatch(app.slice(app.indexOf("async function loadRoute()"), app.indexOf("async function submitLogin()")), /taskAssignees\(\)/)
assert.match(app, /api\.tasks\("all"\)[\s\S]*?homeMineTasks\.value = all\.filter/)
assert.match(app, /loading\.value = !initialRouteResolved/)
const progress = app.match(/async function publishTaskProgress\([\s\S]*?\n}/)?.[0]
assert.ok(progress)
assert.ok(progress.indexOf("replaceTaskInState(published.task)") < progress.indexOf("void extractProgressFacts"))
assert.ok(progress.indexOf("prependUniqueActivity(itemActivities.value, published.activity)") < progress.indexOf("void extractProgressFacts"))
assert.doesNotMatch(progress, /await extractProgressFacts|await refreshExecutionScene|loadRoute\s*\(/)
assert.match(app, /async function extractProgressFacts[\s\S]*?api\.extractActivityFacts/)
const completion = app.match(/async function completeDetailTask\([\s\S]*?\n}/)?.[0]
assert.match(completion, /replaceTaskInState\(completed\.task\)/)
assert.match(completion, /prependUniqueActivity\(itemActivities\.value, completed\.activity\)/)
assert.doesNotMatch(completion, /loadRoute\s*\(/)
const routeLoader = app.slice(app.indexOf("async function loadRoute()"), app.indexOf("async function submitLogin()"))
assert.match(routeLoader, /api\.taskContext\(selectedId\)/)
const detailLoader = routeLoader.slice(routeLoader.indexOf("else if (taskDetailId.value !== null)"), routeLoader.indexOf('else if (routePath === "/tasks")'))
assert.doesNotMatch(detailLoader, /api\.tasks\("all"\)/)
assert.match(routeLoader, /itemActivities\.value = context\.activity_page\.items/)
assert.match(app, /async function loadEarlierDetailActivities[\s\S]*?api\.itemActivityPage/)
const actionRunner = app.match(/async function runTaskAction\([\s\S]*?\n}/)?.[0]
assert.ok(actionRunner)
assert.ok(actionRunner.indexOf("setPendingTaskAction") < actionRunner.indexOf("await request()"))
assert.doesNotMatch(actionRunner, /loading\.value\s*=/)
assert.match(app, /savingFactScopeId\.value = factId/)
assert.match(app, /savingFactScopeId !== null[\s\S]*?保存范围/)
assert.match(api, /taskContext: \(taskId: number\) => request<TaskDetailContext>/)
assert.match(api, /itemActivityPage:/)
assert.match(app, /loader: \(\) => import\("\.\/pages\/TeamPage\.vue"\)/)
assert.match(app, /loader: \(\) => import\("\.\/pages\/KnowledgePage\.vue"\)/)
assert.match(knowledgePage, /emit\("upload", file\)/)
assert.match(teamPage, /emit\("invite"/)

console.log("Local task patching, pending actions, route loading and interaction requests passed")
