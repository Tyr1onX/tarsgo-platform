import assert from "node:assert/strict"
import { readFileSync } from "node:fs"

const dialog = readFileSync(new URL("../src/components/ConfirmDialog.vue", import.meta.url), "utf8")
const app = readFileSync(new URL("../src/App.vue", import.meta.url), "utf8")
const leave = readFileSync(new URL("../src/pages/SchoolLeavePage.vue", import.meta.url), "utf8")
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

// School Leave owns one confirmation state for its three existing flows.
assert.match(leave, /import ConfirmDialog from "\.\.\/components\/ConfirmDialog\.vue"/)
assert.match(leave, /const leaveConfirm = ref<LeaveConfirmRequest \| null>\(null\)/)
assert.match(leave, /<ConfirmDialog[\s\S]*?:open="leaveConfirm !== null"/)

const withdrawRequest = functionSource(leave, "withdrawRequest")
assert.match(withdrawRequest, /title: "撤回请假申请？"/)
assert.match(withdrawRequest, /confirmLabel: "撤回申请"/)
assert.doesNotMatch(withdrawRequest, /danger: true/)
assert.match(withdrawRequest, /api\.withdrawSchoolLeaveRequest\(item\.id\)/)

const cancelRun = functionSource(leave, "cancelRun")
assert.match(cancelRun, /title: "取消本次汇总？"/)
assert.match(cancelRun, /申请会退回待汇总/)
assert.match(cancelRun, /danger: true/)
assert.match(cancelRun, /api\.cancelSchoolLeaveRun\(run\.id\)/)

const deleteRun = functionSource(leave, "deleteRun")
assert.match(deleteRun, /title: "删除已完成记录？"/)
assert.match(deleteRun, /run\.request_count/)
assert.match(deleteRun, /此操作不可恢复/)
assert.match(deleteRun, /danger: true/)
assert.match(deleteRun, /api\.deleteSchoolLeaveRun\(run\.id\)/)

// No business code falls back to the browser-native confirm.
assert.doesNotMatch(app, /window\.confirm/)
assert.doesNotMatch(leave, /window\.confirm/)
assert.equal((app.match(/requestAppConfirmation\(\{/g) ?? []).length, 5)
assert.equal((leave.match(/requestLeaveConfirmation\(\{/g) ?? []).length, 3)

console.log("Unified ConfirmDialog behavior, focus, danger semantics, and eight business migrations passed")
