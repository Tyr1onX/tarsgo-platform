import assert from "node:assert/strict"
import { readFileSync } from "node:fs"

const api = readFileSync(new URL("../src/api.ts", import.meta.url), "utf8")
const app = readFileSync(new URL("../src/App.vue", import.meta.url), "utf8")
const css = readFileSync(new URL("../src/style.css", import.meta.url), "utf8")

assert.match(api, /deleteRootTask: \(rootTaskId: number\) =>\s*request<void>\(`\/api\/tasks\/\$\{rootTaskId\}`, \{ method: "DELETE" \}\)/)
assert.match(app, /function openDeleteRootItemModal\(\)[\s\S]*?isAdmin\.value[\s\S]*?detailTask\.value\?\.parent_id === null/)
assert.match(app, /<section v-if="isAdmin" class="execution-section danger-zone"/)
assert.match(app, /role="dialog" aria-modal="true" aria-labelledby="delete-item-title"/)
assert.match(app, /<h2 id="delete-item-title">删除事项？<\/h2>/)
assert.match(app, /将同时删除此事项下的所有分工、进展记录和当前信息，此操作不可恢复。/)
assert.match(app, /事项<\/dt><dd>\{\{ detailRoot\.title \}\}/)
assert.match(app, /分工<\/dt><dd>\{\{ detailChildren\.length \}\} 项/)
assert.match(app, /动态<\/dt><dd>\{\{ itemActivities\.length \}\} 条/)
assert.match(app, /删除事项<\/button>/)
assert.match(app, /navigateTasks\("all"\)[\s\S]*?showFeedback\("success", "事项已删除"\)/)
assert.match(app, /itemActivities\.value = \[\][\s\S]*?clearFactSuggestions\(\)[\s\S]*?clearItemReview\(\)/)
assert.match(css, /\.danger-modal-backdrop\s*\{[^}]*position:\s*fixed/s)
assert.match(css, /\.danger-action\s*\{[^}]*color:\s*var\(--danger\)/s)

console.log("Root item deletion UI and API wiring passed")
