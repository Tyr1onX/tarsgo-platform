import assert from "node:assert/strict"
import { readFileSync } from "node:fs"

const dialog = readFileSync(new URL("../src/components/ConfirmDialog.vue", import.meta.url), "utf8")
const app = readFileSync(new URL("../src/App.vue", import.meta.url), "utf8")
const leave = readFileSync(new URL("../src/pages/SchoolLeavePage.vue", import.meta.url), "utf8")
const dailyLeave = readFileSync(new URL("../src/pages/DailyLeavePage.vue", import.meta.url), "utf8")
const campLeave = readFileSync(new URL("../src/pages/CampLeavePage.vue", import.meta.url), "utf8")
const knowledge = readFileSync(new URL("../src/pages/KnowledgePage.vue", import.meta.url), "utf8")
const memberDetail = readFileSync(new URL("../src/pages/MemberDetailPage.vue", import.meta.url), "utf8")

const functionSource = (source, name) => {
  const match = source.match(new RegExp(`(?:async )?function ${name}\\b[\\s\\S]*?\\n}`))
  assert.ok(match, `missing ${name}`)
  return match[0]
}

// Shared dialog owns open/cancel/confirm semantics and accessible modal structure.
assert.match(dialog, /defineProps<\{[\s\S]*?open: boolean[\s\S]*?title: string[\s\S]*?description: string/)
assert.match(dialog, /confirmLabel\?: string/)
assert.match(dialog, /cancelLabel\?: string/)
assert.match(dialog, /danger\?: boolean/)
assert.match(dialog, /pending\?: boolean/)
assert.match(dialog, /disabled\?: boolean/)
assert.match(dialog, /v-if="open"/)
assert.match(dialog, /role="dialog"/)
assert.match(dialog, /aria-modal="true"/)
assert.match(dialog, /:aria-labelledby="titleId"/)
assert.match(dialog, /:aria-describedby="descriptionId"/)
assert.match(dialog, /:aria-busy="pending"/)
assert.match(dialog, /emit\("cancel"\)/)
assert.match(dialog, /emit\("confirm"\)/)
assert.match(dialog, /@click\.self="requestClose"/)
assert.match(dialog, /if \(props\.pending\) return[\s\S]*?emit\("cancel"\)/)
assert.match(dialog, /if \(props\.pending \|\| props\.disabled\) return/)
assert.match(dialog, /event\.key === "Escape"/)
assert.match(dialog, /if \(props\.pending\) return/)
assert.match(dialog, /event\.key !== "Tab"/)
assert.match(dialog, /button:not\(:disabled\)/)
assert.match(dialog, /event\.shiftKey && document\.activeElement === first/)
assert.match(dialog, /!event\.shiftKey && document\.activeElement === last/)

// Opening moves focus into the dialog; closing restores the original trigger when it still exists.
assert.match(dialog, /returnFocus\.value = document\.activeElement instanceof HTMLElement/)
assert.match(dialog, /cancelButton\.value\?\.focus\(\)/)
assert.match(dialog, /if \(target\?\.isConnected\) target\.focus\(\)/)
assert.match(dialog, /document\.addEventListener\("keydown", onKeydown\)/)
assert.match(dialog, /document\.removeEventListener\("keydown", onKeydown\)/)

// Normal and danger confirmations are visually distinct without a second dialog implementation.
assert.match(dialog, /:class="\{ danger \}"/)
assert.match(dialog, /\.confirm-dialog-confirm\.danger/)
assert.match(dialog, /color: var\(--danger\)/)
assert.match(dialog, /\.confirm-dialog-confirm \{[\s\S]*?background: var\(--primary-bg\)/)
assert.match(dialog, /box-shadow: 0 6px 20px rgba\(27, 26, 24, 0\.12\)/)
assert.doesNotMatch(dialog, /transform: scale|animation:/)

// 400px layout remains bounded to the viewport.
assert.match(dialog, /width: min\(100%, 420px\)/)
assert.match(dialog, /@media \(max-width: 400px\)/)
assert.match(dialog, /max-width: calc\(100vw - 20px\)/)
assert.doesNotMatch(dialog, /min-width:\s*(?:4\d\d|[5-9]\d\d|\d{4,})px/)

// App owns one confirmation state for shared application confirmations.
assert.match(app, /import ConfirmDialog from "\.\/components\/ConfirmDialog\.vue"/)
assert.match(app, /const appConfirm = ref<ConfirmRequest \| null>\(null\)/)
assert.match(app, /<ConfirmDialog[\s\S]*?:open="appConfirm !== null"/)
assert.match(app, /@cancel="cancelAppConfirmation"/)
assert.match(app, /@confirm="confirmAppConfirmation"/)

// Member disable remains the same API operation and is destructive.
const disableMember = functionSource(app, "disableMember")
assert.match(disableMember, /title: "停用成员？"/)
assert.match(disableMember, /会立即退出登录/)
assert.match(disableMember, /confirmLabel: "停用成员"/)
assert.match(disableMember, /danger: true/)
assert.match(disableMember, /api\.disableMember\(memberId\)/)
assert.match(memberDetail, /emit\(['"]disableMember['"], member\.id\)/)

// Task unclaim remains task-local and is a normal confirmation.
const unclaimTask = functionSource(app, "unclaimTask")
assert.match(unclaimTask, /title: "取消负责人认领？"/)
assert.match(unclaimTask, /重新进入待认领列表/)
assert.match(unclaimTask, /confirmLabel: "取消认领"/)
assert.doesNotMatch(unclaimTask, /danger: true/)
assert.match(unclaimTask, /runTaskAction\(task, "unclaim", \(\) => api\.unclaimTask\(task\.id\)\)/)

// Removing current information keeps history but uses a destructive confirmation.
const removeCurrentFact = functionSource(app, "removeCurrentFact")
assert.match(removeCurrentFact, /title: "移除当前信息？"/)
assert.match(removeCurrentFact, /已有的历史动态会保留/)
assert.match(removeCurrentFact, /danger: true/)
assert.match(removeCurrentFact, /api\.deleteItemFact\(root\.id, factId\)/)

// Knowledge deletion keeps the same API and explains its AI-planning consequence.
const removeKnowledge = functionSource(app, "removeKnowledgeDocument")
assert.match(removeKnowledge, /删除知识条目/)
assert.match(removeKnowledge, /AI 规划将不再使用这份资料/)
assert.match(removeKnowledge, /danger: true/)
assert.match(removeKnowledge, /api\.deleteKnowledgeDocument\(document\.id\)/)
assert.match(knowledge, /emit\(['"]remove['"], document\)/)

// Shared activity closure uses the shared dialog; old summary history is removed from the daily page.
assert.match(dailyLeave, /import ConfirmDialog from "\.\.\/components\/ConfirmDialog\.vue"/)
assert.match(dailyLeave, /<ConfirmDialog[\s\S]*?:open="closeRequest !== null"/)
assert.match(dailyLeave, /关闭共享活动？/)
assert.match(dailyLeave, /closeDailyLeaveWindow\(item\.id\)/)
assert.doesNotMatch(dailyLeave, /LegacySchoolLeaveHistory|旧版日常请假历史/)
assert.match(leave, /<DailyLeavePage/)

// Camp event closure and erroneous participant removal remain confirmed destructive actions.
assert.match(campLeave, /<ConfirmDialog[\s\S]*?:open="confirmation !== null"/)
const closeCampEvent = functionSource(campLeave, "closeEvent")
assert.match(closeCampEvent, /title: "关闭本次报名？"/)
assert.match(closeCampEvent, /danger: true/)
assert.match(closeCampEvent, /api\.closeCampLeaveEvent\(event\.id\)/)
const removeCampParticipant = functionSource(campLeave, "removeParticipant")
assert.match(removeCampParticipant, /title: "移除这条报名？"/)
assert.match(removeCampParticipant, /danger: true/)
assert.match(removeCampParticipant, /api\.removeCampLeaveParticipant\(eventId, participantId\)/)

// No business code falls back to the browser-native confirm.
assert.doesNotMatch(app, /window\.confirm/)
assert.doesNotMatch(leave + dailyLeave + campLeave, /window\.confirm/)
assert.equal((app.match(/requestAppConfirmation\(\{/g) ?? []).length, 5)

console.log("Unified ConfirmDialog behavior, focus, danger semantics, and leave confirmation flows passed")
