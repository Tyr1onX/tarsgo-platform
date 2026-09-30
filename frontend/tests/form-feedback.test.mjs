import assert from "node:assert/strict"
import { readFileSync } from "node:fs"

import { revealInvalidField } from "../src/formFeedback.js"

const calls = []
const field = {
  scrollIntoView(options) { calls.push(["scroll", options]) },
  focus(options) { calls.push(["focus", options]) },
}
const found = revealInvalidField({
  querySelector(selector) {
    assert.equal(selector, '[data-validation-field="task-title"]')
    return field
  },
}, "task-title")
assert.equal(found, field)
assert.deepEqual(calls, [
  ["scroll", { behavior: "smooth", block: "center" }],
  ["focus", { preventScroll: true }],
])
assert.equal(revealInvalidField({ querySelector: () => null }, "missing"), null)

const app = readFileSync(new URL("../src/App.vue", import.meta.url), "utf8")
const css = readFileSync(new URL("../src/style.css", import.meta.url), "utf8")
assert.match(app, /class="toast-layer"/)
assert.match(app, /feedback\.kind === 'error' \? 'alert' : 'status'/)
assert.match(app, /截止时间（可选）[\s\S]*?没有明确时间可以留空。/)
assert.doesNotMatch(app, /data-validation-field="task-deadline"|需要设置截止时间|请补充截止时间/)
assert.match(css, /\.toast-layer\s*\{[^}]*position:\s*fixed/s)
assert.match(css, /env\(safe-area-inset-top\)/)
assert.match(css, /@media \(prefers-color-scheme: dark\)/)
assert.match(css, /\.activity-row p\s*\{[^}]*color:\s*var\(--text\)/s)

console.log("Form feedback, toast, and activity contrast tests passed")
