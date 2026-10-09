import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"

import {
  parseTaskEditorRoute,
  taskEditorCancelPath,
  taskEditorSuccessPath,
  taskEditorTitle,
} from "../src/taskRoutes.js"

const app = await readFile(new URL("../src/App.vue", import.meta.url), "utf8")
const css = await readFile(new URL("../src/style.css", import.meta.url), "utf8")

const editorStart = app.indexOf('<template v-else-if="isTaskEditorRoute">')
const homeStart = app.indexOf('<template v-else-if="path === \'/\'">', editorStart)
const tasksStart = app.indexOf('<template v-else-if="path === \'/tasks\'">')
const nextTasksRoute = app.indexOf('<template v-else-if="path === \'/me\'">', tasksStart)
assert.ok(editorStart >= 0 && homeStart > editorStart && tasksStart > homeStart && nextTasksRoute > tasksStart)

const editor = app.slice(editorStart, homeStart)
const taskList = app.slice(tasksStart, nextTasksRoute)

// The list is a browse and execution surface with no embedded form.
assert.doesNotMatch(taskList, /<form\b|taskTitle|taskDeadline|taskOwnerId|taskEditor/)
assert.doesNotMatch(taskList, /AI 规划任务|手动创建/)
assert.doesNotMatch(app, /startAIPlanner|planFromBase|generateAIPlan|refineAIPlan/)
assert.doesNotMatch(app, /taskFormOpen|closeTaskForm/)

// The single editor route covers root create, child create, and both edit kinds.
assert.match(editor, /← 返回/)
assert.match(editor, /taskEditorHeading/)
assert.match(editor, /分工属于：\{\{ parentTask\.title \}\}/)
assert.match(editor, /@submit\.prevent="submitTask"/)
assert.match(editor, /:disabled="taskSaving"/)
assert.match(app, /function startChildTask\(parent: Task\)[\s\S]*?navigate\(`\/tasks\/\$\{parent\.id\}\/new-child`\)/)
assert.match(app, /navigate\(`\/tasks\/\$\{task\.id\}\/edit`\)/)
assert.match(app, /function editTaskFromDetail\(task: Task\)[\s\S]*?void editTask\(task\)/)
assert.match(app, /function taskMenuActions\(task: Task\)[\s\S]*?label: task\.parent_id === null \? "编辑事项" : "编辑分工"/)

// Route helpers define context-sensitive titles, cancel paths, and save destinations.
assert.equal(parseTaskEditorRoute("/tasks/new"), null)
assert.deepEqual(parseTaskEditorRoute("/tasks/12/new-child"), { kind: "new-child", parentId: 12 })
assert.deepEqual(parseTaskEditorRoute("/tasks/34/edit"), { kind: "edit", taskId: 34 })
assert.equal(parseTaskEditorRoute("/tasks/12"), null)
assert.equal(taskEditorTitle(parseTaskEditorRoute("/tasks/12/new-child")), "添加分工")
assert.equal(taskEditorTitle(parseTaskEditorRoute("/tasks/34/edit"), false), "编辑事项")
assert.equal(taskEditorTitle(parseTaskEditorRoute("/tasks/34/edit"), true), "编辑分工")
assert.equal(taskEditorCancelPath(parseTaskEditorRoute("/tasks/12/new-child")), "/tasks/12")
assert.equal(taskEditorCancelPath(parseTaskEditorRoute("/tasks/34/edit")), "/tasks/34")
assert.equal(taskEditorSuccessPath(parseTaskEditorRoute("/tasks/12/new-child")), "/tasks/12")
assert.equal(taskEditorSuccessPath(parseTaskEditorRoute("/tasks/34/edit")), "/tasks/34")
assert.match(app, /navigate\(destination, \{ replace: true \}\)/)
assert.match(app, /navigate\(taskEditorSuccessPath\(taskEditor\.value\), \{ replace: true \}\)/)

// Existing task fields, validation, and advanced disclosure remain in one form.
for (const model of [
  "taskTitle",
  "taskOwnerMode",
  "taskOwnerId",
  "taskOwnerClaimable",
  "taskDeadline",
  "taskDeliverable",
  "taskExecutionPointsText",
  "taskCautionsText",
  "taskPrerequisitesText",
  "taskDependencyIds",
  "taskCollaboratorIds",
  "taskCollaborationOpen",
  "taskStatus",
]) {
  assert.ok(editor.includes(`v-model="${model}"`), `missing ${model}`)
}
assert.match(editor, /<details class="advanced-fields">[\s\S]*?<summary>/)
assert.doesNotMatch(editor.match(/<details class="advanced-fields">[\s\S]*?<\/details>/)?.[0] ?? "", /\sopen(?:\s|>)/)
assert.match(app, /taskLineLimitMessage\(\)/)
assert.match(app, /showFieldError\("task-title"/)
assert.match(app, /showFieldError\("task-owner"/)
assert.match(app, /api\.updateTask\(editingTaskId\.value, payload\)/)
assert.match(app, /api\.createTask\(\{/)

// Published task maintenance and status control stay available; the editor remains narrow and mobile-safe.
assert.match(app, /function editTaskFromDetail\(task: Task\)[\s\S]*?void editTask\(task\)/)
assert.match(app, /api\.createTask\(\{/)
assert.match(taskList, /TaskStatusIndicator/)
assert.match(css, /\.task-editor-form\s*\{[^}]*min-width:\s*0/)
assert.match(css, /\.task-editor-form input,[\s\S]*?max-width:\s*100%/)
assert.match(css, /\.task-editor-save\s*\{[^}]*width:\s*fit-content/)
assert.match(css, /@media \(max-width: 560px\)[\s\S]*?\.task-editor-form\s*\{[^}]*padding-bottom:[^}]*safe-area-inset-bottom/s)
assert.match(css, /html,[\s\S]*?body\s*\{\s*min-width:\s*320px/)

console.log("Task editor route and list separation tests passed")
