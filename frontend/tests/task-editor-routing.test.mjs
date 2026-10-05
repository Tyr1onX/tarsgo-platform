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
assert.match(taskList, /AI 规划任务/)
assert.match(taskList, /@click="startNewTask\(\)"/) // manual creation remains available
assert.doesNotMatch(app, /taskFormOpen|closeTaskForm/)

// The single editor route covers root create, child create, and both edit kinds.
assert.match(editor, /← 返回/)
assert.match(editor, /taskEditorHeading/)
assert.match(editor, /分工属于：\{\{ parentTask\.title \}\}/)
assert.match(editor, /@submit\.prevent="submitTask"/)
assert.match(editor, /:disabled="taskSaving"/)
assert.match(app, /navigate\(parent \? `\/tasks\/\$\{parent\.id\}\/new-child` : "\/tasks\/new"\)/)
assert.match(app, /navigate\(`\/tasks\/\$\{task\.id\}\/edit`\)/)
assert.match(app, /function editTaskFromDetail\(task: Task\)[\s\S]*?void editTask\(task\)/)
assert.match(app, /function taskMenuActions\(task: Task\)[\s\S]*?label: task\.parent_id === null \? "编辑事项" : "编辑分工"/)

// Route helpers define context-sensitive titles, cancel paths, and save destinations.
assert.deepEqual(parseTaskEditorRoute("/tasks/new"), { kind: "new-root" })
assert.deepEqual(parseTaskEditorRoute("/tasks/12/new-child"), { kind: "new-child", parentId: 12 })
assert.deepEqual(parseTaskEditorRoute("/tasks/34/edit"), { kind: "edit", taskId: 34 })
assert.equal(parseTaskEditorRoute("/tasks/12"), null)
assert.equal(taskEditorTitle(parseTaskEditorRoute("/tasks/new")), "新建事项")
assert.equal(taskEditorTitle(parseTaskEditorRoute("/tasks/12/new-child")), "添加分工")
assert.equal(taskEditorTitle(parseTaskEditorRoute("/tasks/34/edit"), false), "编辑事项")
assert.equal(taskEditorTitle(parseTaskEditorRoute("/tasks/34/edit"), true), "编辑分工")
assert.equal(taskEditorCancelPath(parseTaskEditorRoute("/tasks/new")), "/tasks")
assert.equal(taskEditorCancelPath(parseTaskEditorRoute("/tasks/12/new-child")), "/tasks/12")
assert.equal(taskEditorCancelPath(parseTaskEditorRoute("/tasks/34/edit")), "/tasks/34")
assert.equal(taskEditorSuccessPath(parseTaskEditorRoute("/tasks/new"), 56), "/tasks/56")
assert.equal(taskEditorSuccessPath(parseTaskEditorRoute("/tasks/12/new-child"), 57), "/tasks/12")
assert.equal(taskEditorSuccessPath(parseTaskEditorRoute("/tasks/34/edit"), 34), "/tasks/34")
assert.match(app, /navigate\(destination, \{ replace: true \}\)/)
assert.match(app, /navigate\(taskEditorSuccessPath\(taskEditor\.value, updatedTask\.id\), \{ replace: true \}\)/)

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

// Planner entry and status control stay available; the task editor remains narrow and mobile-safe.
assert.match(app, /function startAIPlanner\(\)[\s\S]*?navigate\("\/ai-planner"\)/)
assert.match(taskList, /TaskStatusIndicator/)
assert.match(css, /\.task-editor-form\s*\{[^}]*min-width:\s*0/)
assert.match(css, /\.task-editor-form input,[\s\S]*?max-width:\s*100%/)
assert.match(css, /\.task-editor-save\s*\{[^}]*width:\s*fit-content/)
assert.match(css, /@media \(max-width: 560px\)[\s\S]*?\.task-editor-form\s*\{[^}]*padding-bottom:[^}]*safe-area-inset-bottom/s)
assert.match(css, /html,[\s\S]*?body\s*\{\s*min-width:\s*320px/)

console.log("Task editor route and list separation tests passed")
