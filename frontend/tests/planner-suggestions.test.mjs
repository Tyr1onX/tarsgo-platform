import assert from "node:assert/strict"
import { readFileSync } from "node:fs"

import {
  filterIgnoredPlannerSuggestions,
  ignorePlannerSuggestion,
  plannerSuggestionJoinInstruction,
  plannerSuggestionKey,
} from "../src/plannerSuggestions.js"

const suggestion = {
  title: "战队周边展示",
  reason: "类似科技展示曾使用少量战队周边作为展台展示，本次描述尚未提及。",
}
const draft = {
  suggestions: [
    suggestion,
    { title: "另一个提醒", reason: "仅用于测试当前 session 过滤。" },
  ],
}
const ignored = new Set()

ignorePlannerSuggestion(draft, 0, ignored)
assert.equal(draft.suggestions.length, 1)
assert.equal(ignored.size, 1)
assert.ok(ignored.has(plannerSuggestionKey(suggestion)))

const regenerated = {
  suggestions: [suggestion, { title: "新提醒", reason: "仍可显示。" }],
}
filterIgnoredPlannerSuggestions(regenerated, ignored)
assert.deepEqual(regenerated.suggestions.map((item) => item.title), ["新提醒"])

const instruction = plannerSuggestionJoinInstruction(suggestion)
assert.match(instruction, /负责人已确认/)
assert.match(instruction, /纳入本次事项/)
assert.match(instruction, /不要再把它保留为 suggestion/)
assert.match(instruction, /不要扩展到未确认的相邻用途/)
assert.doesNotMatch(instruction, /是否需要/)

const appSource = readFileSync(new URL("../src/App.vue", import.meta.url), "utf8")
assert.match(appSource, /v-if="plannerDraft\.suggestions\.length"/)
assert.match(appSource, /@click="dismissPlannerSuggestion\(index\)"/)
assert.match(appSource, /@click="addPlannerSuggestion\(suggestion\)"/)

console.log("Planner suggestion frontend tests passed")