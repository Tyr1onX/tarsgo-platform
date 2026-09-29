import assert from "node:assert/strict"

import {
  defaultFactSelection,
  executionSummary,
  isCurrentFactSuggestionRequest,
  preserveEditableDraft,
  sourceTaskTitle,
} from "../src/execution.js"

const children = [
  { id: 1, status: "done", blocked: false },
  { id: 2, status: "doing", blocked: false },
  { id: 3, status: "todo", blocked: true },
  { id: 4, status: "todo", blocked: false },
]
assert.deepEqual(executionSummary(children), {
  total: 4,
  done: 1,
  doing: 1,
  todo: 2,
  blocked: 1,
  label: "1 / 4 已完成",
  detail: "1 项进行中 · 2 项未开始",
})
assert.deepEqual(executionSummary([]).total, 0)
assert.equal(sourceTaskTitle({ task_id: 2 }, [{ id: 2, title: "确认来访时间" }]), "确认来访时间")
assert.equal(sourceTaskTitle({ task_id: null }, []), "")
assert.deepEqual(defaultFactSelection([{ text: "时间" }, { text: "地点" }, { text: "时间" }]), ["时间", "地点"])
assert.equal(preserveEditableDraft("正在编辑", "服务端新值", true), "正在编辑")
assert.equal(preserveEditableDraft("旧值", "服务端新值", false), "服务端新值")
assert.equal(isCurrentFactSuggestionRequest(10, 10, 3, 3), true)
assert.equal(isCurrentFactSuggestionRequest(10, 11, 3, 3), false)
assert.equal(isCurrentFactSuggestionRequest(10, 10, 3, 4), false)

console.log("Shared execution frontend helpers passed")
