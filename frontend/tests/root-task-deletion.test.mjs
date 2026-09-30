import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { isExpandedRoot, removeRootAndChildren, toggleExpandedRoot } from "../src/rootItemList.js"

const api = readFileSync(new URL("../src/api.ts", import.meta.url), "utf8")
const app = readFileSync(new URL("../src/App.vue", import.meta.url), "utf8")
const css = readFileSync(new URL("../src/style.css", import.meta.url), "utf8")

assert.match(api, /deleteRootTask: \(rootTaskId: number\) =>\s*request<void>\(`\/api\/tasks\/\$\{rootTaskId\}`, \{ method: "DELETE" \}\)/)
assert.match(app, /function openDeleteRootItemModal\(root = detailRoot\.value, origin: "detail" \| "list" = "detail"\)/)
assert.match(app, /<section v-if="isAdmin" class="execution-section danger-zone"/)
assert.match(app, /role="dialog" aria-modal="true" aria-labelledby="delete-item-title"/)
assert.match(app, /<h2 id="delete-item-title">删除事项？<\/h2>/)
assert.match(app, /将同时删除此事项下的所有分工、进展记录和当前信息，此操作不可恢复。/)
assert.match(app, /事项<\/dt><dd>\{\{ deleteTargetRoot\.title \}\}/)
assert.match(app, /分工<\/dt><dd>\{\{ deleteTargetChildren\.length \}\} 项/)
assert.match(app, /deleteTargetActivityLoading[\s\S]*?deleteTargetActivityCount/)
assert.match(app, /删除事项<\/button>/)
assert.match(app, /if \(origin === "detail"\) \{[\s\S]*?navigateTasks\("all"\)[\s\S]*?\} else \{[\s\S]*?api\.tasks\(taskView\.value\)/)
assert.match(app, /openDeleteRootItemModal\(task, 'list'\)/)
assert.match(app, /@click="openDeleteRootItemModal">删除事项<\/button>/)
assert.match(app, /showFeedback\("success", "事项已删除"\)/)
assert.match(app, /itemActivities\.value = \[\][\s\S]*?clearFactSuggestions\(\)[\s\S]*?clearItemReview\(\)/)
assert.match(css, /\.danger-modal-backdrop\s*\{[^}]*position:\s*fixed/s)
assert.match(css, /\.danger-action\s*\{[^}]*color:\s*var\(--danger\)/s)

const initiallyExpanded = new Set()
assert.equal(isExpandedRoot(initiallyExpanded, 11), false)
const withFirstExpanded = toggleExpandedRoot(initiallyExpanded, 11)
const withBothExpanded = toggleExpandedRoot(withFirstExpanded, 22)
assert.equal(isExpandedRoot(withBothExpanded, 11), true)
assert.equal(isExpandedRoot(withBothExpanded, 22), true)
assert.equal(isExpandedRoot(toggleExpandedRoot(withBothExpanded, 11), 11), false)
assert.equal(isExpandedRoot(toggleExpandedRoot(withBothExpanded, 11), 22), true)

const listStart = app.indexOf('<article v-for="task in rootTasks"')
const orphanStart = app.indexOf('<article v-for="task in orphanTasks"', listStart)
const rootList = app.slice(listStart, orphanStart)
assert.match(rootList, /<button class="task-title-link" type="button" @click="openTaskDetail\(task\)">/)
assert.match(rootList, /:aria-expanded="isRootExpanded\(task\.id\)"/)
assert.match(rootList, /展开分工 ▾/)
assert.match(rootList, /收起分工 ▴/)
assert.match(rootList, /<span v-else class="no-child-tasks">暂无分工<\/span>/)
assert.match(rootList, /v-if="isManager" type="button" @click="editTask\(task\)">编辑<\/button>/)
assert.match(rootList, /v-if="isAdmin" class="danger-text" type="button" @click\.stop="openDeleteRootItemModal\(task, 'list'\)">删除<\/button>/)
assert.match(rootList, /v-if="childTasks\(task\.id\)\.length && isRootExpanded\(task\.id\)"[\s\S]*?class="work-breakdown"/)
assert.match(rootList, /root-progress-summary[\s\S]*?executionSummary\(childTasks\(task\.id\)\)\.blocked/)
assert.match(rootList, /<div v-if="isManager" class="status-actions root-status-actions">/)
assert.equal((rootList.match(/class="danger-text"/g) ?? []).length, 1)
assert.ok(rootList.indexOf('class="danger-text"') < rootList.indexOf('<article v-for="child'))
const orphanList = app.slice(orphanStart)
assert.doesNotMatch(orphanList.slice(0, orphanList.indexOf("<div v-else class=\"empty empty-action")), /class="status-actions"/)
assert.match(css, /@media \(max-width: 860px\)[\s\S]*?\.operation-card-top\s*\{\s*grid-template-columns: minmax\(0, 1fr\)/)

const tasks = [
  { id: 1, parent_id: null },
  { id: 2, parent_id: 1 },
  { id: 3, parent_id: 1 },
  { id: 4, parent_id: null },
  { id: 5, parent_id: 4 },
]
assert.deepEqual(removeRootAndChildren(tasks, 1).map((task) => task.id), [4, 5])

console.log("Root item list expand/collapse, delete modal reuse, and API wiring passed")
