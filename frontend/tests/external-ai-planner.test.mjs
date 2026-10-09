import assert from "node:assert/strict"
import { readFileSync } from "node:fs"

import { buildExternalAIPlannerPrompt, parseExternalAIPlannerDraft } from "../src/externalAIPlanner.js"

const prompt = buildExternalAIPlannerPrompt({
  description: "10 月 11 日举办微专业宣讲会，整理必要的现场分工。",
  currentEventContext: "文件《流程.txt》：签到安排由学院提供。",
})
assert.match(prompt, /10 月 11 日举办微专业宣讲会/)
assert.match(prompt, /文件《流程\.txt》：签到安排由学院提供/)
assert.match(prompt, /责任单元/)
assert.match(prompt, /deadline.*null/)
assert.match(prompt, /owner_claimable/)
assert.match(prompt, /collaboration_open/)
assert.match(prompt, /只输出一段可解析的原始 JSON/)
assert.match(prompt, /不输出负责人姓名、成员、owner_id/)

const validDraft = {
  item: { title: "微专业宣讲会", deliverable: "", deadline: null },
  tasks: [{
    title: "完成现场引导",
    deliverable: "参会者按流程到达宣讲区域。",
    deadline: "2026-10-11T08:00",
    execution_points: ["按确认流程引导参会者"],
    cautions: [],
    prerequisites: [],
    owner_claimable: true,
    collaboration_open: false,
  }],
  questions: [],
}
const parsed = parseExternalAIPlannerDraft(JSON.stringify(validDraft))
assert.equal(parsed.ok, true)
if (parsed.ok) {
  assert.equal(parsed.draft.item.title, "微专业宣讲会")
  assert.equal(parsed.draft.tasks[0].deadline, "2026-10-11T08:00")
  assert.deepEqual(parsed.draft.suggestions, [])
}

const malformed = parseExternalAIPlannerDraft('{"item":')
assert.equal(malformed.ok, false)
if (!malformed.ok) assert.match(malformed.error, /^JSON 语法错误：/)

const extraOwner = structuredClone(validDraft)
extraOwner.tasks[0].owner_id = 42
const ownerResult = parseExternalAIPlannerDraft(JSON.stringify(extraOwner))
assert.equal(ownerResult.ok, false)
if (!ownerResult.ok) assert.match(ownerResult.error, /tasks\[0\]\.owner_id/)

const invalidDeadline = structuredClone(validDraft)
invalidDeadline.tasks[0].deadline = "下周"
const deadlineResult = parseExternalAIPlannerDraft(JSON.stringify(invalidDeadline))
assert.equal(deadlineResult.ok, false)
if (!deadlineResult.ok) assert.match(deadlineResult.error, /tasks\[0\]\.deadline/)

const tooManyPoints = structuredClone(validDraft)
tooManyPoints.tasks[0].execution_points = Array.from({ length: 7 }, (_, index) => `步骤 ${index + 1}`)
const pointsResult = parseExternalAIPlannerDraft(JSON.stringify(tooManyPoints))
assert.equal(pointsResult.ok, false)
if (!pointsResult.ok) assert.match(pointsResult.error, /execution_points 最多 6 条/)

const badType = structuredClone(validDraft)
badType.tasks[0].owner_claimable = "true"
const typeResult = parseExternalAIPlannerDraft(JSON.stringify(badType))
assert.equal(typeResult.ok, false)
if (!typeResult.ok) assert.match(typeResult.error, /tasks\[0\]\.owner_claimable 必须是布尔值/)

const appSource = readFileSync(new URL("../src/App.vue", import.meta.url), "utf8")
assert.match(appSource, /class="planner-composer base-composer"/)
assert.match(appSource, /复制 AI 提示词/)
assert.match(appSource, /导入 AI 方案/)
assert.match(appSource, /function importExternalAIPlanner\(\)[\s\S]*?setPlannerDraft\(result\.draft\)[\s\S]*?navigate\("\/planner-draft"\)/)
assert.doesNotMatch(appSource.match(/function importExternalAIPlanner\(\)[\s\S]*?\n}/)?.[0] ?? "", /api\./)
assert.match(appSource, /请核对并手动确认创建/)
assert.doesNotMatch(appSource, /generateAIPlan|refineAIPlan|startAIPlanner|planFromBase/)

console.log("External AI planner prompt and import validation passed")
