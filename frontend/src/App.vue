<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue"

import { ApiError, api } from "./api"
import { revealInvalidField } from "./formFeedback.js"
import { filterIgnoredPlannerSuggestions, ignorePlannerSuggestion, plannerSuggestionJoinInstruction } from "./plannerSuggestions.js"
import { itemReviewChanges, removeItemReviewSuggestion } from "./itemReview.js"
import {
  defaultFactSelection,
  executionSummary,
  isCurrentFactSuggestionRequest,
  preserveEditableDraft,
  sourceTaskTitle,
} from "./execution.js"
import type {
  AIPlannerDraft,
  AIPlannerExtractedFile,
  AIPlannerSuggestionDraft,
  AIPlannerTaskDraft,
  AIItemReviewSuggestion,
  AIItemFactSuggestion,
  InvitationInfo,
  InviteResult,
  ItemActivity,
  ItemFact,
  ItemFactInput,
  ItemFactScope,
  KnowledgeDocument,
  KnowledgeSyncSummary,
  Member,
  MemberSummary,
  Role,
  Task,
  TaskStatus,
  TaskView,
} from "./types"

const path = ref(window.location.pathname)
const user = ref<Member | null>(null)
const loading = ref(true)
const routeNotFound = ref(false)
const error = ref("")
const notice = ref("")
const fieldErrors = ref<Record<string, string>>({})
const feedback = ref<{ kind: "success" | "error" | "info"; message: string } | null>(null)
let feedbackTimer: number | undefined

const loginEmail = ref("")
const loginPassword = ref("")

const invitation = ref<InvitationInfo | null>(null)
const invitePassword = ref("")
const invitePasswordConfirm = ref("")

const tasks = ref<Task[]>([])
const homeMineTasks = ref<Task[]>([])
const homeAllTasks = ref<Task[]>([])
const itemActivities = ref<ItemActivity[]>([])
const members = ref<Member[]>([])
const taskMembers = ref<MemberSummary[]>([])
const latestInvite = ref<InviteResult | null>(null)
const taskView = ref<TaskView>("mine")
const claimableCount = ref(0)
const aiPlannerAvailable = ref(false)
const plannerDescription = ref("")
const plannerAttachments = ref<{ id: string; filename: string; extracted_text: string }[]>([])
const plannerAttachmentMessage = ref("")
const plannerUploading = ref(false)
const plannerDragActive = ref(false)
const plannerFileInput = ref<HTMLInputElement | null>(null)
const plannerDraft = ref<AIPlannerDraft | null>(null)
const plannerGenerating = ref(false)
const plannerPublishing = ref(false)
const plannerTaskDetailsText = ref<{ execution_points: string; cautions: string; prerequisites: string }[]>([])
const plannerSelectedTaskIndex = ref<number | null>(null)
const plannerNewTaskIndex = ref<number | null>(null)
const plannerEmptyDetailSection = ref<"execution_points" | "cautions" | "prerequisites" | null>(null)
const plannerDetailScrollTop = ref(0)
const plannerDetailCloseButton = ref<HTMLButtonElement | null>(null)
const plannerDetailBackButton = ref<HTMLButtonElement | null>(null)
const plannerDetailTitleInput = ref<HTMLInputElement | null>(null)
const plannerAddTaskButton = ref<HTMLButtonElement | null>(null)
const plannerRefineOpenIndex = ref<number | null>(null)
const plannerRefineInstruction = ref("")
const plannerGlobalInstruction = ref("")
const plannerRefining = ref(false)
const plannerIgnoredSuggestionKeys = new Set<string>()
const knowledgeDocuments = ref<KnowledgeDocument[]>([])
const knowledgeUploading = ref(false)
const knowledgeSyncing = ref(false)
const knowledgeSyncSummary = ref<KnowledgeSyncSummary | null>(null)
const knowledgeUploadRef = ref<HTMLInputElement | null>(null)

const itemActivityDraft = ref("")
const itemActivityAddToFacts = ref(false)
const itemActivityFactScope = ref<ItemFactScope>("global")
const itemActivityRelatedTaskIds = ref<number[]>([])
const itemFactDraft = ref("")
const itemFactScope = ref<ItemFactScope>("global")
const itemFactRelatedTaskIds = ref<number[]>([])
const editingFactScopeId = ref<number | null>(null)
const editingFactScope = ref<ItemFactScope>("global")
const editingFactTaskIds = ref<number[]>([])
const taskResultDraft = ref("")
const taskProgressDraft = ref("")
const taskCompletionDraft = ref("")
const taskCompletionSync = ref(false)
const taskProgressSaving = ref(false)
const taskCompletionSaving = ref(false)
const factExtractionLoading = ref(false)
const factSuggestions = ref<AIItemFactSuggestion[]>([])
const selectedFactSuggestions = ref<string[]>([])
const confirmedFactSupersessions = ref<string[]>([])
const factSuggestionActivityId = ref<number | null>(null)
const itemReviewSummary = ref("")
const itemReviewSuggestions = ref<{ key: string; suggestion: AIItemReviewSuggestion }[]>([])
const itemReviewLoading = ref(false)
const itemReviewApplyingKey = ref("")
let itemReviewEpoch = 0
let factExtractionEpoch = 0
let collaborationRefreshTimer: number | undefined
let collaborationRefreshInFlight = false
let lastCollaborationRefreshAt = 0

const memberName = ref("")
const memberEmail = ref("")
const memberRole = ref<Role>("member")

const taskFormOpen = ref(false)
const editingTaskId = ref<number | null>(null)
const parentTaskId = ref<number | null>(null)
const taskTitle = ref("")
const taskDeliverable = ref("")
const taskExecutionPointsText = ref("")
const taskCautionsText = ref("")
const taskPrerequisitesText = ref("")
const taskCautionsOpen = ref(false)
const taskPrerequisitesOpen = ref(false)
const taskOwnerMode = ref<"assigned" | "claimable">("assigned")
const taskOwnerId = ref<number | null>(null)
const taskOwnerClaimable = ref(false)
const taskCollaboratorIds = ref<number[]>([])
const taskCollaborationOpen = ref(false)
const taskDeadline = ref("")
const taskStatus = ref<TaskStatus>("todo")
const taskDependencyIds = ref<number[]>([])

const isAdmin = computed(() => user.value?.role === "admin")
const isManager = computed(
  () => user.value?.role === "admin" || user.value?.role === "manager",
)
const inviteToken = computed(() =>
  path.value.startsWith("/invite/") ? path.value.slice("/invite/".length) : "",
)
const activeMembers = computed(() => taskMembers.value)
const activeMemberIds = computed(() => new Set(activeMembers.value.map((member) => member.id)))
const editingTask = computed(
  () => tasks.value.find((task) => task.id === editingTaskId.value) ?? null,
)
const plannerSelectedTask = computed(() => {
  const index = plannerSelectedTaskIndex.value
  return index === null ? null : plannerDraft.value?.tasks[index] ?? null
})
const parentTask = computed(
  () => tasks.value.find((task) => task.id === parentTaskId.value) ?? null,
)
const ownerOptions = computed(() => {
  const options = [...activeMembers.value]
  const owner = editingTask.value?.owner
  if (owner && !activeMemberIds.value.has(owner.id)) options.unshift(owner)
  return options
})
const taskDetailId = computed(() => {
  const match = path.value.match(/^\/tasks\/(\d+)$/)
  return match ? Number(match[1]) : null
})
const detailTask = computed(() =>
  taskDetailId.value === null ? null : tasks.value.find((task) => task.id === taskDetailId.value) ?? null,
)
const detailRoot = computed(() => {
  const task = detailTask.value
  if (!task) return null
  return task.parent_id === null
    ? task
    : tasks.value.find((candidate) => candidate.id === task.parent_id) ?? null
})
const detailChildren = computed(() =>
  detailRoot.value ? tasks.value.filter((task) => task.parent_id === detailRoot.value?.id) : [],
)
const detailProgress = computed(() => executionSummary(detailChildren.value))
const recentItemFacts = computed(() => [...(detailTask.value?.item_facts ?? [])].slice(-4).reverse())
const detailTaskActivities = computed(() =>
  itemActivities.value,
)
const canManageFactScope = computed(() => Boolean(
  detailRoot.value && (isManager.value || detailRoot.value.owner?.id === user.value?.id),
))
const canWriteDetailItem = computed(() => {
  const root = detailRoot.value
  const currentId = user.value?.id
  if (!root || !currentId) return false
  if (isManager.value || root.owner?.id === currentId) return true
  return detailChildren.value.some(
    (task) => task.owner?.id === currentId || task.collaborators.some((member) => member.id === currentId),
  )
})
const canEditDetailResult = computed(
  () => Boolean(detailTask.value && isManager.value),
)
const canPublishTaskProgress = computed(() => {
  const task = detailTask.value
  const currentId = user.value?.id
  return Boolean(
    task && task.parent_id !== null && task.status !== "done" && !task.blocked && currentId &&
    (isManager.value || task.owner?.id === currentId || task.collaborators.some((person) => person.id === currentId)),
  )
})
const canCompleteDetailTask = computed(() =>
  Boolean(detailTask.value && detailTask.value.parent_id !== null && detailTask.value.status !== "done" && !detailTask.value.blocked &&
    (isManager.value || detailTask.value.owner?.id === user.value?.id)),
)
const availableDependencyTasks = computed(() =>
  parentTaskId.value === null
    ? []
    : tasks.value.filter((task) => task.parent_id === parentTaskId.value && task.id !== editingTaskId.value),
)

const homeOpenTasks = computed(() => homeMineTasks.value.filter((task) => task.status !== "done"))
const homeTaskCards = computed(() => {
  const allChildren = new Set(
    homeAllTasks.value.filter((task) => task.parent_id !== null).map((task) => task.parent_id as number),
  )
  const children = homeOpenTasks.value.filter((task) => task.parent_id !== null)
  const standaloneRoots = homeOpenTasks.value.filter(
    (task) => task.parent_id === null && !allChildren.has(task.id),
  )
  return [...children, ...standaloneRoots].sort(
    (left, right) => new Date(left.deadline).getTime() - new Date(right.deadline).getTime(),
  )
})
const rootTasks = computed(() => tasks.value.filter((task) => task.parent_id === null))
const loadedTaskIds = computed(() => new Set(tasks.value.map((task) => task.id)))
const orphanTasks = computed(() =>
  tasks.value.filter(
    (task) => task.parent_id !== null && !loadedTaskIds.value.has(task.parent_id),
  ),
)

const statusLabels: Record<TaskStatus, string> = {
  todo: "待开始",
  doing: "进行中",
  done: "已完成",
}
const reviewProposalSections = [
  { label: "执行提示", field: "execution_points" },
  { label: "注意事项", field: "cautions" },
  { label: "开始前需要", field: "prerequisites" },
] as const

const roleLabels: Record<Role, string> = {
  admin: "管理员",
  manager: "任务管理员",
  member: "成员",
}

const viewLabels: Record<TaskView, string> = {
  mine: "我的",
  claimable: "待认领",
  all: "全部",
}

function messageOf(reason: unknown): string {
  return reason instanceof Error ? reason.message : "操作失败"
}

function clearFeedback() {
  if (feedbackTimer !== undefined) window.clearTimeout(feedbackTimer)
  feedbackTimer = undefined
  feedback.value = null
}

function showFeedback(kind: "success" | "error" | "info", message: string) {
  clearFeedback()
  feedback.value = { kind, message }
  if (kind !== "error") {
    feedbackTimer = window.setTimeout(clearFeedback, 3_500)
  } else {
    feedbackTimer = window.setTimeout(clearFeedback, 7_000)
  }
}

watch(error, (message) => {
  if (message) showFeedback("error", message)
})
watch(notice, (message) => {
  if (message) showFeedback("success", message)
})
watch(path, (nextPath, previousPath) => {
  if (nextPath === previousPath) return
  fieldErrors.value = {}
  error.value = ""
  showAllDetailActivities.value = false
  if (feedback.value?.kind === "error") clearFeedback()
})

function clearFieldError(field: string) {
  if (!fieldErrors.value[field]) return
  const next = { ...fieldErrors.value }
  delete next[field]
  fieldErrors.value = next
}

async function showFieldError(field: string, toastMessage: string, inlineMessage: string) {
  fieldErrors.value = { ...fieldErrors.value, [field]: inlineMessage }
  error.value = toastMessage
  if (field.startsWith("planner-item-")) {
    document.querySelector<HTMLDetailsElement>(".planner-item-edit")?.setAttribute("open", "")
  }
  const taskTitleMatch = field.match(/^planner-task-title-(\d+)$/)
  if (taskTitleMatch) plannerSelectedTaskIndex.value = Number(taskTitleMatch[1])
  if (field === "planner-task-details") {
    const match = toastMessage.match(/第 (\d+) 项(怎么做|注意|开始前需要)/)
    if (match) {
      plannerSelectedTaskIndex.value = Number(match[1]) - 1
      plannerEmptyDetailSection.value = match[2] === "怎么做" ? "execution_points" :
        match[2] === "注意" ? "cautions" : "prerequisites"
    }
  }
  await nextTick()
  const targetField = field === "planner-task-details" ?
    plannerEmptyDetailSection.value === "execution_points" ? "planner-execution-points" :
      plannerEmptyDetailSection.value === "cautions" ? "planner-cautions" : "planner-prerequisites" : field
  revealInvalidField(document, targetField)
}

function ensureFactRelatedSelection(scope: ItemFactScope, taskIds: number[]) {
  if (scope !== "related" || taskIds.length || !detailTask.value) return taskIds
  const currentTaskId = detailTask.value.parent_id === null ? null : detailTask.value.id
  return currentTaskId ? [currentTaskId] : detailChildren.value.slice(0, 1).map((task) => task.id)
}

function ensureFactSuggestionTasks(index: number) {
  const suggestion = factSuggestions.value[index]
  if (!suggestion || suggestion.scope !== "related" || suggestion.related_task_ids.length) return
  suggestion.related_task_ids = ensureFactRelatedSelection("related", [])
}

function factScopeDescription(fact: ItemFact) {
  if (fact.scope === "global") return "整个事项"
  return `相关工作 · ${fact.related_tasks.map((task) => task.title).join("、")}`
}

function toggleActivityFactScope(scope: ItemFactScope) {
  itemActivityFactScope.value = scope
  itemActivityRelatedTaskIds.value = ensureFactRelatedSelection(scope, itemActivityRelatedTaskIds.value)
}

function toggleNewFactScope(scope: ItemFactScope) {
  itemFactScope.value = scope
  itemFactRelatedTaskIds.value = ensureFactRelatedSelection(scope, itemFactRelatedTaskIds.value)
}

const showAllDetailActivities = ref(false)
const visibleDetailActivities = computed(() =>
  showAllDetailActivities.value ? detailTaskActivities.value : detailTaskActivities.value.slice(0, 5),
)

function navigate(nextPath: string) {
  const nextRoute = nextPath.split("?")[0]
  const wasTaskDetail = /^\/tasks\/\d+$/.test(path.value)
  const isNextTaskDetail = /^\/tasks\/\d+$/.test(nextRoute)
  if (path.value !== nextRoute && (wasTaskDetail || isNextTaskDetail)) {
    clearFactSuggestions()
    taskProgressDraft.value = ""
    taskCompletionDraft.value = ""
    taskCompletionSync.value = false
  }
  if (taskDetailId.value !== null && nextRoute !== path.value) clearItemReview()
  if (window.location.pathname + window.location.search !== nextPath) {
    window.history.pushState({}, "", nextPath)
  }
  path.value = window.location.pathname
  syncCollaborationRefreshTimer()
  error.value = ""
  showAllDetailActivities.value = false
  fieldErrors.value = {}
  if (feedback.value?.kind === "error") clearFeedback()
  void loadRoute()
}

function clearItemReview() {
  itemReviewEpoch += 1
  itemReviewSummary.value = ""
  itemReviewSuggestions.value = []
  itemReviewApplyingKey.value = ""
}

function clearFactSuggestions() {
  factExtractionEpoch += 1
  factSuggestions.value = []
  selectedFactSuggestions.value = []
  confirmedFactSupersessions.value = []
  factSuggestionActivityId.value = null
  factExtractionLoading.value = false
}

async function refreshExecutionScene(force = false) {
  const taskId = taskDetailId.value
  const selected = detailTask.value
  if (taskId === null || !selected || document.visibilityState !== "visible" || collaborationRefreshInFlight) return
  const now = Date.now()
  if (!force && now - lastCollaborationRefreshAt < 2_000) return
  lastCollaborationRefreshAt = now
  collaborationRefreshInFlight = true
  const routeAtStart = path.value
  const rootId = selected.parent_id ?? selected.id
  try {
    const [freshTasks, freshActivities] = await Promise.all([
      api.tasks("all"),
      api.itemActivities(rootId),
    ])
    if (path.value !== routeAtStart || taskDetailId.value !== taskId) return
    const previousTask = tasks.value.find((task) => task.id === taskId)
    const resultDraftDirty = Boolean(previousTask && taskResultDraft.value !== (previousTask.result ?? ""))
    tasks.value = freshTasks
    const refreshedTask = freshTasks.find((task) => task.id === taskId)
    if (refreshedTask) {
      taskResultDraft.value = preserveEditableDraft(
        taskResultDraft.value,
        refreshedTask.result ?? "",
        resultDraftDirty,
      )
    }
    itemActivities.value = freshActivities
  } catch {
    // Background refresh is best effort; preserve the current view and draft text.
  } finally {
    collaborationRefreshInFlight = false
  }
}

function handleExecutionRefreshSignal() {
  void refreshExecutionScene()
}

function syncCollaborationRefreshTimer() {
  if (collaborationRefreshTimer !== undefined) {
    window.clearInterval(collaborationRefreshTimer)
    collaborationRefreshTimer = undefined
  }
  if (/^\/tasks\/\d+$/.test(path.value)) {
    collaborationRefreshTimer = window.setInterval(() => {
      void refreshExecutionScene()
    }, 60_000)
  }
}

async function reviewCurrentItemPlan() {
  const root = detailTask.value
  if (!root || root.parent_id !== null || !aiPlannerAvailable.value || itemReviewLoading.value) return
  error.value = ""
  itemReviewLoading.value = true
  clearItemReview()
  const epoch = itemReviewEpoch
  try {
    const result = await api.reviewItemPlan(root.id)
    if (epoch !== itemReviewEpoch) return
    itemReviewSummary.value = result.summary
    itemReviewSuggestions.value = result.suggestions.map((suggestion, index) => ({
      key: `${Date.now()}-${index}-${Math.random().toString(36).slice(2)}`,
      suggestion,
    }))
  } catch (reason) {
    error.value = messageOf(reason)
  } finally {
    itemReviewLoading.value = false
  }
}

function dismissItemReviewSuggestion(key: string) {
  itemReviewSuggestions.value = removeItemReviewSuggestion(itemReviewSuggestions.value, key)
}

function changesForReviewSuggestion(suggestion: AIItemReviewSuggestion) {
  const current = detailChildren.value.find((task) => task.id === suggestion.target_task_id)
  return itemReviewChanges(current, suggestion.proposed_task)
}

async function applyItemReviewSuggestion(entry: { key: string; suggestion: AIItemReviewSuggestion }) {
  const root = detailTask.value
  if (!root || root.parent_id !== null || !isManager.value || itemReviewApplyingKey.value) return
  error.value = ""
  itemReviewApplyingKey.value = entry.key
  try {
    const applied = await api.applyItemReview(root.id, entry.suggestion)
    const existingIndex = tasks.value.findIndex((task) => task.id === applied.task.id)
    if (existingIndex >= 0) tasks.value.splice(existingIndex, 1, applied.task)
    else tasks.value.push(applied.task)
    itemActivities.value = [applied.activity, ...itemActivities.value]
    itemReviewSuggestions.value = removeItemReviewSuggestion(itemReviewSuggestions.value, entry.key)
    notice.value = "已应用这条方案调整"
  } catch (reason) {
    error.value = messageOf(reason)
  } finally {
    itemReviewApplyingKey.value = ""
  }
}

function readTaskView(): TaskView {
  const value = new URLSearchParams(window.location.search).get("view")
  return value === "claimable" || value === "all" ? value : "mine"
}

function navigateTasks(view: TaskView) {
  const url = view === "mine" ? "/tasks" : `/tasks?view=${view}`
  taskView.value = view
  navigate(url)
}

function formatDate(value: string) {
  return new Date(value).toLocaleString("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

function toLocalInput(value: string) {
  return value.slice(0, 16)
}

function childTasks(parentId: number) {
  return tasks.value.filter((task) => task.parent_id === parentId)
}

function homeRoot(task: Task) {
  if (task.parent_id === null) return task
  return homeAllTasks.value.find((candidate) => candidate.id === task.parent_id) ?? null
}

function openTaskDetail(task: Task) {
  navigate(`/tasks/${task.id}`)
}

function taskDetailSections(task: Task) {
  const executionHints = [
    ...(task.execution_points ?? []),
    ...(task.cautions ?? []).map((item) => `注意：${item}`),
  ]
  return [
    { title: "执行提示", items: executionHints },
    { title: "开始前需要", items: task.prerequisites ?? [] },
  ].filter((section) => section.items.length)
}

function parseTaskLines(value: string) {
  return value.split("\n").map((line) => line.trim()).filter(Boolean)
}

function taskLineLimitMessage() {
  if (parentTaskId.value === null) return ""
  const limits = [
    [taskExecutionPointsText.value, 6, "怎么做"],
    [taskCautionsText.value, 5, "注意"],
    [taskPrerequisitesText.value, 4, "开始前需要"],
  ] as const
  for (const [value, max, label] of limits) {
    const lines = parseTaskLines(value)
    if (lines.length > max) return `${label}最多填写 ${max} 条。`
    if (lines.some((line) => line.length > 240)) return `${label}每条最多 240 字。`
  }
  return ""
}

function isCollaborator(task: Task) {
  return task.collaborators.some((member) => member.id === user.value?.id)
}

function resetTaskForm() {
  editingTaskId.value = null
  parentTaskId.value = null
  taskTitle.value = ""
  taskDeliverable.value = ""
  taskExecutionPointsText.value = ""
  taskCautionsText.value = ""
  taskPrerequisitesText.value = ""
  taskCautionsOpen.value = false
  taskPrerequisitesOpen.value = false
  taskOwnerMode.value = "assigned"
  taskOwnerId.value = activeMembers.value[0]?.id ?? null
  taskOwnerClaimable.value = false
  taskCollaboratorIds.value = []
  taskCollaborationOpen.value = false
  taskDeadline.value = ""
  taskStatus.value = "todo"
  taskDependencyIds.value = []
}

function closeTaskForm() {
  taskFormOpen.value = false
  resetTaskForm()
}

function startNewTask(parent?: Task) {
  resetTaskForm()
  if (parent) {
    parentTaskId.value = parent.id
    taskDeadline.value = toLocalInput(parent.deadline)
  }
  taskFormOpen.value = true
  if (path.value !== "/tasks" || taskView.value !== "all") {
    navigateTasks("all")
  } else {
    window.scrollTo({ top: 0, behavior: "smooth" })
  }
}

function editTask(task: Task) {
  taskFormOpen.value = true
  editingTaskId.value = task.id
  parentTaskId.value = task.parent_id
  taskTitle.value = task.title
  taskDeliverable.value = task.deliverable
  taskExecutionPointsText.value = (task.execution_points ?? []).join("\n")
  taskCautionsText.value = (task.cautions ?? []).join("\n")
  taskPrerequisitesText.value = (task.prerequisites ?? []).join("\n")
  taskCautionsOpen.value = Boolean(taskCautionsText.value.trim())
  taskPrerequisitesOpen.value = Boolean(taskPrerequisitesText.value.trim())
  taskOwnerMode.value = task.owner ? "assigned" : "claimable"
  taskOwnerId.value = task.owner?.id ?? activeMembers.value[0]?.id ?? null
  taskOwnerClaimable.value = task.owner_claimable
  taskCollaboratorIds.value = task.collaborators
    .filter((member) => activeMemberIds.value.has(member.id))
    .map((member) => member.id)
  taskCollaborationOpen.value = task.collaboration_open
  taskDeadline.value = toLocalInput(task.deadline)
  taskStatus.value = task.status
  taskDependencyIds.value = task.depends_on_tasks.map((dependency) => dependency.id)
  window.scrollTo({ top: 0, behavior: "smooth" })
}

function sameIds(left: number[], right: number[]) {
  const sortedLeft = [...left].sort((a, b) => a - b)
  const sortedRight = [...right].sort((a, b) => a - b)
  return (
    sortedLeft.length === sortedRight.length &&
    sortedLeft.every((id, index) => id === sortedRight[index])
  )
}

async function loadPlannerAccess() {
  aiPlannerAvailable.value = false
  if (user.value?.role !== "admin") return
  try {
    const access = await api.aiPlannerAccess()
    aiPlannerAvailable.value = access.available
  } catch {
    aiPlannerAvailable.value = false
  }
}

async function loadKnowledgeDocuments() {
  knowledgeDocuments.value = await api.knowledgeDocuments()
}

async function loadCurrentUser() {
  try {
    user.value = await api.me()
    await loadPlannerAccess()
  } catch (reason) {
    if (reason instanceof ApiError && reason.status === 401) {
      user.value = null
      return
    }
    throw reason
  }
}

async function loadRoute() {
  loading.value = true
  routeNotFound.value = false
  error.value = ""

  try {
    const publicPage = path.value === "/login" || path.value.startsWith("/invite/")
    if (!publicPage && !user.value) {
      await loadCurrentUser()
      if (!user.value) {
        navigate("/login")
        return
      }
    }

    if (path.value === "/login") {
      if (user.value) {
        navigate("/")
        return
      }
    } else if (path.value.startsWith("/invite/")) {
      invitation.value = await api.invitation(inviteToken.value)
    } else if (path.value === "/admin/tasks") {
      navigate("/tasks")
      return
    } else if (path.value === "/admin/members") {
      navigate("/team")
      return
    } else if (path.value === "/") {
      const [mine, claimable, all] = await Promise.all([
        api.tasks("mine"),
        api.tasks("claimable"),
        api.tasks("all"),
      ])
      homeMineTasks.value = mine
      homeAllTasks.value = all
      claimableCount.value = claimable.length
    } else if (taskDetailId.value !== null) {
      if (isManager.value) {
        ;[taskMembers.value, tasks.value] = await Promise.all([
          api.taskAssignees(),
          api.tasks("all"),
        ])
      } else {
        tasks.value = await api.tasks("all")
      }
      const selected = tasks.value.find((task) => task.id === taskDetailId.value)
      if (!selected) {
        routeNotFound.value = true
        return
      }
      taskResultDraft.value = selected.result ?? ""
      itemFactDraft.value = ""
      itemActivityDraft.value = ""
      itemActivityAddToFacts.value = false
      const rootId = selected.parent_id ?? selected.id
      itemActivities.value = await api.itemActivities(rootId)
    } else if (path.value === "/tasks") {
      taskView.value = readTaskView()
      if (isManager.value) {
        ;[taskMembers.value, tasks.value] = await Promise.all([
          api.taskAssignees(),
          api.tasks(taskView.value),
        ])
        if (!taskOwnerId.value) taskOwnerId.value = activeMembers.value[0]?.id ?? null
      } else {
        tasks.value = await api.tasks(taskView.value)
      }
    } else if (path.value === "/ai-planner") {
      if (!isAdmin.value || !aiPlannerAvailable.value) {
        navigate("/")
        return
      }
    } else if (path.value === "/knowledge") {
      if (!isAdmin.value) {
        navigate("/")
        return
      }
      await loadKnowledgeDocuments()
    } else if (path.value === "/team") {
      if (!isAdmin.value) {
        navigate("/")
        return
      }
      members.value = await api.members()
    } else if (path.value === "/me") {
      // Current user data is already sufficient.
    } else {
      routeNotFound.value = true
    }
  } catch (reason) {
    if (reason instanceof ApiError && reason.status === 401 && !path.value.startsWith("/invite/")) {
      user.value = null
      navigate("/login")
      return
    }
    error.value = messageOf(reason)
  } finally {
    loading.value = false
  }
}

async function submitLogin() {
  error.value = ""
  notice.value = ""
  try {
    user.value = await api.login(loginEmail.value, loginPassword.value)
    await loadPlannerAccess()
    loginPassword.value = ""
    navigate("/")
  } catch (reason) {
    error.value = messageOf(reason)
  }
}

async function submitInvitation() {
  error.value = ""
  if (invitePassword.value !== invitePasswordConfirm.value) {
    error.value = "两次输入的密码不一致"
    return
  }

  try {
    await api.acceptInvitation(inviteToken.value, invitePassword.value)
    invitation.value = null
    invitePassword.value = ""
    invitePasswordConfirm.value = ""
    notice.value = "密码已设置，请登录"
    navigate("/login")
  } catch (reason) {
    error.value = messageOf(reason)
  }
}

async function submitMemberInvite() {
  error.value = ""
  try {
    latestInvite.value = await api.inviteMember(
      memberName.value,
      memberEmail.value,
      memberRole.value,
    )
    memberName.value = ""
    memberEmail.value = ""
    memberRole.value = "member"
    members.value = await api.members()
  } catch (reason) {
    error.value = messageOf(reason)
  }
}

async function regenerateInvite(memberId: number) {
  error.value = ""
  try {
    latestInvite.value = await api.regenerateInvite(memberId)
  } catch (reason) {
    error.value = messageOf(reason)
  }
}

async function copyInvite() {
  if (!latestInvite.value) return
  await navigator.clipboard.writeText(window.location.origin + latestInvite.value.invite_path)
  notice.value = "邀请链接已复制"
}

async function disableMember(memberId: number) {
  if (!window.confirm("停用后该成员会立即退出登录，确定停用？")) return
  error.value = ""
  try {
    await api.disableMember(memberId)
    members.value = await api.members()
  } catch (reason) {
    error.value = messageOf(reason)
  }
}

async function enableMember(memberId: number) {
  error.value = ""
  try {
    await api.enableMember(memberId)
    members.value = await api.members()
  } catch (reason) {
    error.value = messageOf(reason)
  }
}

async function submitTask() {
  error.value = ""
  fieldErrors.value = {}
  const desiredOwnerId = taskOwnerMode.value === "assigned" ? taskOwnerId.value : null
  const desiredOwnerClaimable =
    taskOwnerMode.value === "claimable" ? true : taskOwnerClaimable.value

  if (!taskTitle.value.trim()) {
    await showFieldError("task-title", "请填写任务标题", "需要填写任务标题")
    return
  }
  if (!taskDeadline.value) {
    await showFieldError("task-deadline", "请补充截止时间", "需要设置截止时间")
    return
  }
  if (taskOwnerMode.value === "assigned" && !desiredOwnerId) {
    await showFieldError("task-owner", "请选择负责人", "需要选择负责人")
    return
  }
  const lineLimitError = taskLineLimitMessage()
  if (lineLimitError) {
    const field = lineLimitError.includes("注意") ? "task-cautions" :
      lineLimitError.includes("开始前") ? "task-prerequisites" : "task-execution-points"
    await showFieldError(field, lineLimitError, lineLimitError)
    return
  }
  const executionPoints = parseTaskLines(taskExecutionPointsText.value)
  const cautions = parseTaskLines(taskCautionsText.value)
  const prerequisites = parseTaskLines(taskPrerequisitesText.value)

  try {
    if (editingTaskId.value) {
      const original = editingTask.value
      if (!original) return

      const payload: Parameters<typeof api.updateTask>[1] = {}
      if (taskTitle.value !== original.title) payload.title = taskTitle.value
      if (taskDeliverable.value !== original.deliverable) payload.deliverable = taskDeliverable.value
      if (JSON.stringify(executionPoints) !== JSON.stringify(original.execution_points ?? [])) payload.execution_points = executionPoints
      if (JSON.stringify(cautions) !== JSON.stringify(original.cautions ?? [])) payload.cautions = cautions
      if (JSON.stringify(prerequisites) !== JSON.stringify(original.prerequisites ?? [])) payload.prerequisites = prerequisites
      if (desiredOwnerId !== original.owner?.id) payload.owner_id = desiredOwnerId
      if (desiredOwnerClaimable !== original.owner_claimable) {
        payload.owner_claimable = desiredOwnerClaimable
      }
      if (taskCollaborationOpen.value !== original.collaboration_open) {
        payload.collaboration_open = taskCollaborationOpen.value
      }
      if (taskDeadline.value !== toLocalInput(original.deadline)) {
        payload.deadline = taskDeadline.value
      }
      if (taskStatus.value !== original.status) payload.status = taskStatus.value
      if (!sameIds(taskDependencyIds.value, original.depends_on_tasks.map((dependency) => dependency.id))) {
        payload.depends_on_task_ids = taskDependencyIds.value
      }

      const originalActiveCollaborators = original.collaborators
        .filter((member) => activeMemberIds.value.has(member.id))
        .map((member) => member.id)
      if (!sameIds(taskCollaboratorIds.value, originalActiveCollaborators)) {
        payload.collaborator_ids = taskCollaboratorIds.value
      }

      if (Object.keys(payload).length) {
        await api.updateTask(editingTaskId.value, payload)
      }
    } else {
      await api.createTask({
        parent_id: parentTaskId.value,
        title: taskTitle.value,
        deliverable: taskDeliverable.value,
        execution_points: executionPoints,
        cautions,
        prerequisites,
        owner_id: desiredOwnerId,
        owner_claimable: desiredOwnerClaimable,
        collaborator_ids: taskCollaboratorIds.value,
        collaboration_open: taskCollaborationOpen.value,
        deadline: taskDeadline.value,
        status: taskStatus.value,
        depends_on_task_ids: taskDependencyIds.value,
      })
    }

    clearItemReview()
    closeTaskForm()
    taskView.value = "all"
    if (window.location.search !== "?view=all") {
      window.history.replaceState({}, "", "/tasks?view=all")
    }
    await loadRoute()
  } catch (reason) {
    error.value = messageOf(reason)
  }
}

async function updateOwnTaskStatus(task: Task, status: TaskStatus) {
  error.value = ""
  try {
    await api.updateTask(task.id, { status })
    clearItemReview()
    await loadRoute()
  } catch (reason) {
    error.value = messageOf(reason)
  }
}

async function claimTask(task: Task) {
  error.value = ""
  try {
    await api.claimTask(task.id)
    clearItemReview()
    await loadRoute()
  } catch (reason) {
    error.value = messageOf(reason)
  }
}

async function unclaimTask(task: Task) {
  if (!window.confirm("取消负责人认领后，该任务会重新进入待认领列表。确定继续？")) return
  error.value = ""
  try {
    await api.unclaimTask(task.id)
    clearItemReview()
    await loadRoute()
  } catch (reason) {
    error.value = messageOf(reason)
  }
}

async function joinTask(task: Task) {
  error.value = ""
  try {
    await api.joinTask(task.id)
    clearItemReview()
    await loadRoute()
  } catch (reason) {
    error.value = messageOf(reason)
  }
}

async function leaveTask(task: Task) {
  error.value = ""
  try {
    await api.leaveTask(task.id)
    clearItemReview()
    await loadRoute()
  } catch (reason) {
    error.value = messageOf(reason)
  }
}


async function planFromBase() {
  if (plannerDescription.value.trim().length < 10) {
    error.value = "请先补充一些事项背景，再生成方案。"
    return
  }
  if (window.location.pathname !== "/ai-planner") {
    window.history.pushState({}, "", "/ai-planner")
  }
  path.value = "/ai-planner"
  await generateAIPlan()
}

async function saveTaskResult() {
  const task = detailTask.value
  if (!task || !canEditDetailResult.value) return
  error.value = ""
  try {
    await api.updateTask(task.id, { result: taskResultDraft.value })
    clearItemReview()
    notice.value = "执行结果已保存"
    await loadRoute()
  } catch (reason) {
    error.value = messageOf(reason)
  }
}

async function publishTaskProgress() {
  const task = detailTask.value
  const content = taskProgressDraft.value.trim()
  if (!task || !content || !canPublishTaskProgress.value || taskProgressSaving.value) return
  error.value = ""
  clearFactSuggestions()
  taskProgressSaving.value = true
  const epoch = factExtractionEpoch
  try {
    const published = await api.publishTaskProgress(task.id, content)
    taskProgressDraft.value = ""
    clearItemReview()
    notice.value = "进展已发布"
    await refreshExecutionScene(true)

    if (isCurrentFactSuggestionRequest(task.id, taskDetailId.value, epoch, factExtractionEpoch)) {
      factExtractionLoading.value = true
    }
    try {
      const extracted = await api.extractActivityFacts(published.task.parent_id as number, published.activity.id)
      if (isCurrentFactSuggestionRequest(task.id, taskDetailId.value, epoch, factExtractionEpoch)) {
        factSuggestions.value = extracted.suggestions
        selectedFactSuggestions.value = defaultFactSelection(extracted.suggestions)
        factSuggestionActivityId.value = published.activity.id
        if (extracted.suggestions.length) {
          notice.value = `进展已发布，有 ${extracted.suggestions.length} 条信息可能需要同步给团队`
        }
      }
    } catch {
      if (isCurrentFactSuggestionRequest(task.id, taskDetailId.value, epoch, factExtractionEpoch)) {
        notice.value = "进展已发布，暂时无法提取可同步信息"
      }
    } finally {
      if (isCurrentFactSuggestionRequest(task.id, taskDetailId.value, epoch, factExtractionEpoch)) {
        factExtractionLoading.value = false
      }
    }
  } catch (reason) {
    error.value = messageOf(reason)
  } finally {
    taskProgressSaving.value = false
  }
}

async function addSuggestedFactsToItem() {
  const root = detailRoot.value
  const chosen = factSuggestions.value.filter((suggestion) => selectedFactSuggestions.value.includes(suggestion.text))
  if (!root || !chosen.length || !canWriteDetailItem.value || factSuggestionActivityId.value === null) return
  error.value = ""
  try {
    const facts: ItemFactInput[] = chosen.map((suggestion) => ({
      content: suggestion.text,
      scope: suggestion.scope,
      related_task_ids: suggestion.scope === "related" ? suggestion.related_task_ids : [],
      source_activity_id: factSuggestionActivityId.value,
      supersedes_fact_id: canManageFactScope.value && confirmedFactSupersessions.value.includes(suggestion.text)
        ? suggestion.supersedes_fact_id
        : null,
    }))
    await api.addScopedFactsBatch(root.id, facts)
    clearFactSuggestions()
    clearItemReview()
    notice.value = "已按确认范围同步信息"
    await refreshExecutionScene(true)
  } catch (reason) {
    error.value = messageOf(reason)
  }
}

function dismissFactSuggestions() {
  clearFactSuggestions()
}

async function completeDetailTask() {
  const task = detailTask.value
  const result = taskCompletionDraft.value.trim()
  if (!task || !result || !canCompleteDetailTask.value || taskCompletionSaving.value) return
  if (taskCompletionSync.value && result.length > 500) {
    error.value = "同步到事项信息的最终结果最多 500 字。"
    return
  }
  error.value = ""
  taskCompletionSaving.value = true
  try {
    await api.completeTask(task.id, result, taskCompletionSync.value)
    taskCompletionDraft.value = ""
    taskCompletionSync.value = false
    clearFactSuggestions()
    clearItemReview()
    notice.value = "任务已完成"
    await refreshExecutionScene(true)
  } catch (reason) {
    error.value = messageOf(reason)
  } finally {
    taskCompletionSaving.value = false
  }
}

async function addCurrentFact() {
  const root = detailRoot.value
  const content = itemFactDraft.value.trim()
  if (!root || !content || !canWriteDetailItem.value) return
  error.value = ""
  try {
    await api.addScopedFactsBatch(root.id, [{
      content,
      scope: itemFactScope.value,
      related_task_ids: itemFactScope.value === "related" ? itemFactRelatedTaskIds.value : [],
    }])
    clearItemReview()
    itemFactDraft.value = ""
    itemFactScope.value = "global"
    itemFactRelatedTaskIds.value = []
    await loadRoute()
  } catch (reason) {
    error.value = messageOf(reason)
  }
}

async function removeCurrentFact(factId: number) {
  const root = detailRoot.value
  if (!root || !canManageFactScope.value) return
  if (!window.confirm("移除这条当前信息？已有的历史动态会保留。")) return
  error.value = ""
  try {
    await api.deleteItemFact(root.id, factId)
    clearItemReview()
    await loadRoute()
  } catch (reason) {
    error.value = messageOf(reason)
  }
}

function beginFactScopeEdit(fact: ItemFact) {
  editingFactScopeId.value = fact.id
  editingFactScope.value = fact.scope
  editingFactTaskIds.value = fact.related_tasks.map((task) => task.id)
}

function cancelFactScopeEdit() {
  editingFactScopeId.value = null
  editingFactTaskIds.value = []
}

async function saveFactScope(factId: number) {
  const root = detailRoot.value
  if (!root || !canManageFactScope.value) return
  error.value = ""
  try {
    await api.updateFactScope(
      root.id,
      factId,
      editingFactScope.value,
      editingFactScope.value === "related" ? editingFactTaskIds.value : [],
    )
    cancelFactScopeEdit()
    await loadRoute()
  } catch (reason) {
    error.value = messageOf(reason)
  }
}

async function recordItemActivity() {
  const root = detailRoot.value
  const content = itemActivityDraft.value.trim()
  if (!root || !content || !canWriteDetailItem.value) return
  if (itemActivityAddToFacts.value && content.length > 500) {
    error.value = "加入当前信息时，单条最多 500 字。"
    return
  }
  if (itemActivityAddToFacts.value && itemActivityFactScope.value === "related" && !itemActivityRelatedTaskIds.value.length) {
    error.value = "请选择至少一个相关分工"
    return
  }
  error.value = ""
  try {
    await api.addItemActivity(
      root.id,
      content,
      itemActivityAddToFacts.value,
      itemActivityFactScope.value,
      itemActivityFactScope.value === "related" ? itemActivityRelatedTaskIds.value : [],
    )
    clearItemReview()
    itemActivityDraft.value = ""
    itemActivityAddToFacts.value = false
    itemActivityFactScope.value = "global"
    itemActivityRelatedTaskIds.value = []
    await loadRoute()
  } catch (reason) {
    error.value = messageOf(reason)
  }
}

async function addResultToContext() {
  const task = detailTask.value
  if (!task || !task.result || !canWriteDetailItem.value) return
  error.value = ""
  try {
    await api.taskResultToContext(task.id)
    clearItemReview()
    notice.value = "执行结果已加入事项信息"
    await loadRoute()
  } catch (reason) {
    error.value = messageOf(reason)
  }
}

function editTaskFromDetail(task: Task) {
  if (!isManager.value) return
  clearItemReview()
  taskView.value = "all"
  window.history.pushState({}, "", "/tasks?view=all")
  path.value = "/tasks"
  editTask(task)
}

function startAIPlanner() {
  if (!plannerDraft.value) plannerIgnoredSuggestionKeys.clear()
  error.value = ""
  navigate("/ai-planner")
}

const PLANNER_FILE_EXTENSIONS = new Set([".md", ".txt", ".docx", ".pdf"])
const PLANNER_MAX_FILE_BYTES = 10 * 1024 * 1024
const PLANNER_MAX_FILES = 5
const PLANNER_MAX_CURRENT_CONTEXT_CHARS = 5_000

const fullPlannerAttachmentContext = computed(() =>
  plannerAttachments.value
    .map((attachment) => `文件《${attachment.filename}》：\n${attachment.extracted_text}`)
    .join("\n\n"),
)
const plannerAttachmentContext = computed(() =>
  fullPlannerAttachmentContext.value.slice(0, PLANNER_MAX_CURRENT_CONTEXT_CHARS),
)
const plannerAttachmentContextTruncated = computed(
  () => fullPlannerAttachmentContext.value.length > PLANNER_MAX_CURRENT_CONTEXT_CHARS,
)

function choosePlannerFiles() {
  plannerFileInput.value?.click()
}

function removePlannerAttachment(id: string) {
  plannerAttachments.value = plannerAttachments.value.filter((attachment) => attachment.id !== id)
}

async function addPlannerFiles(files: File[]) {
  plannerAttachmentMessage.value = ""
  error.value = ""
  if (plannerUploading.value) return
  plannerUploading.value = true
  try {
    for (const file of files) {
      if (plannerAttachments.value.length >= PLANNER_MAX_FILES) {
        plannerAttachmentMessage.value = `本次最多添加 ${PLANNER_MAX_FILES} 个文件。`
        break
      }
      const extension = file.name.slice(file.name.lastIndexOf(".")).toLowerCase()
      if (!PLANNER_FILE_EXTENSIONS.has(extension)) {
        plannerAttachmentMessage.value = `不支持“${file.name}”，请选择 md、txt、docx 或 pdf 文件。`
        continue
      }
      if (file.size > PLANNER_MAX_FILE_BYTES) {
        plannerAttachmentMessage.value = `“${file.name}”超过 10 MiB，无法添加。`
        continue
      }
      try {
        const result: AIPlannerExtractedFile = await api.extractPlannerFile(file)
        if (!result.extracted_text.trim() || result.parse_status === "failed" || result.parse_status === "unparseable") {
          plannerAttachmentMessage.value = `“${result.filename}”${result.error ? `：${result.error}` : "无法提取文字"}`
          continue
        }
        plannerAttachments.value.push({
          id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
          filename: result.filename,
          extracted_text: result.extracted_text,
        })
        if (result.parse_status === "truncated") {
          plannerAttachmentMessage.value = `“${result.filename}”内容较长，已提取可处理部分。`
        }
      } catch (reason) {
        plannerAttachmentMessage.value = `“${file.name}”添加失败：${messageOf(reason)}`
      }
    }
  } finally {
    plannerUploading.value = false
  }
}

function onPlannerFilesSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  input.value = ""
  void addPlannerFiles(files)
}

function onPlannerDragOver(event: DragEvent) {
  if (event.dataTransfer?.types.includes("Files")) plannerDragActive.value = true
}

function onPlannerDragLeave(event: DragEvent) {
  const target = event.currentTarget
  if (target instanceof HTMLElement && event.relatedTarget instanceof Node && target.contains(event.relatedTarget)) return
  plannerDragActive.value = false
}

function onPlannerDrop(event: DragEvent) {
  event.preventDefault()
  plannerDragActive.value = false
  const files = Array.from(event.dataTransfer?.files ?? [])
  if (files.length) void addPlannerFiles(files)
}

function editPlannerRequest() {
  plannerDraft.value = null
  plannerSelectedTaskIndex.value = null
  plannerNewTaskIndex.value = null
  plannerRefineOpenIndex.value = null
  error.value = ""
}

function newPlannerTask(): AIPlannerTaskDraft {
  return {
    title: "",
    deliverable: "",
    execution_points: [],
    cautions: [],
    prerequisites: [],
    owner_claimable: true,
    collaboration_open: false,
  }
}

function addPlannerTask() {
  if (!plannerDraft.value) return
  const index = plannerDraft.value.tasks.length
  plannerDraft.value.tasks.push(newPlannerTask())
  plannerTaskDetailsText.value.push({ execution_points: "", cautions: "", prerequisites: "" })
  plannerNewTaskIndex.value = index
  openPlannerTaskDetail(index, true)
}

function removePlannerTask(index: number) {
  plannerDraft.value?.tasks.splice(index, 1)
  plannerTaskDetailsText.value.splice(index, 1)
  if (plannerNewTaskIndex.value === index) plannerNewTaskIndex.value = null
  else if (plannerNewTaskIndex.value !== null && plannerNewTaskIndex.value > index) plannerNewTaskIndex.value -= 1
  if (plannerSelectedTaskIndex.value === index) plannerSelectedTaskIndex.value = null
  else if (plannerSelectedTaskIndex.value !== null && plannerSelectedTaskIndex.value > index) plannerSelectedTaskIndex.value -= 1
  if (plannerRefineOpenIndex.value === index) plannerRefineOpenIndex.value = null
  else if (plannerRefineOpenIndex.value !== null && plannerRefineOpenIndex.value > index) plannerRefineOpenIndex.value -= 1
}

function plannerTaskStatus(task: AIPlannerTaskDraft) {
  return [task.owner_claimable ? "待认领" : "", task.collaboration_open ? "开放协作" : ""]
    .filter(Boolean)
    .join(" · ")
}

function openPlannerTaskDetail(index: number, focusTitle = false) {
  if (!plannerDraft.value?.tasks[index]) return
  plannerDetailScrollTop.value = window.scrollY
  plannerSelectedTaskIndex.value = index
  plannerEmptyDetailSection.value = null
  void nextTick(() => {
    if (focusTitle) plannerDetailTitleInput.value?.focus()
    else if (window.matchMedia("(max-width: 1100px)").matches) plannerDetailBackButton.value?.focus()
    else plannerDetailCloseButton.value?.focus()
  })
}

function isEmptyNewPlannerTask(index: number) {
  const task = plannerDraft.value?.tasks[index]
  const detail = plannerTaskDetailsText.value[index]
  return Boolean(
    task && detail &&
    !task.title.trim() &&
    !task.deliverable.trim() &&
    !parseTaskLines(detail.execution_points).length &&
    !parseTaskLines(detail.cautions).length &&
    !parseTaskLines(detail.prerequisites).length &&
    task.owner_claimable &&
    !task.collaboration_open,
  )
}

function closePlannerTaskDetail() {
  const index = plannerSelectedTaskIndex.value
  if (index === null) return
  const shouldRemoveEmptyNewTask = plannerNewTaskIndex.value === index && isEmptyNewPlannerTask(index)
  plannerSelectedTaskIndex.value = null
  plannerEmptyDetailSection.value = null
  if (shouldRemoveEmptyNewTask) removePlannerTask(index)
  void nextTick(() => {
    window.scrollTo(0, plannerDetailScrollTop.value)
    const focusIndex = shouldRemoveEmptyNewTask
      ? Math.min(index, Math.max((plannerDraft.value?.tasks.length ?? 1) - 1, 0))
      : index
    const card = document.querySelector<HTMLButtonElement>(`[data-planner-task-index="${focusIndex}"]`)
    if (card) card.focus()
    else plannerAddTaskButton.value?.focus()
  })
}

function deleteSelectedPlannerTask() {
  const index = plannerSelectedTaskIndex.value
  if (index === null) return
  plannerSelectedTaskIndex.value = null
  plannerEmptyDetailSection.value = null
  removePlannerTask(index)
  void nextTick(() => {
    window.scrollTo(0, plannerDetailScrollTop.value)
    const nextIndex = Math.min(index, Math.max((plannerDraft.value?.tasks.length ?? 1) - 1, 0))
    const card = document.querySelector<HTMLButtonElement>(`[data-planner-task-index="${nextIndex}"]`)
    if (card) card.focus()
    else plannerAddTaskButton.value?.focus()
  })
}

function openPlannerEmptyDetailSection(section: "execution_points" | "cautions" | "prerequisites") {
  plannerEmptyDetailSection.value = section
  void nextTick(() => {
    const field = document.querySelector<HTMLTextAreaElement>(`[data-planner-detail-field="${section}"]`)
    field?.focus()
  })
}

function handlePlannerDetailKeydown(event: KeyboardEvent) {
  if (event.key === "Escape" && plannerSelectedTaskIndex.value !== null) {
    event.preventDefault()
    closePlannerTaskDetail()
  }
}

function resetPlannerTaskDetails(draft: AIPlannerDraft) {
  plannerTaskDetailsText.value = draft.tasks.map((task) => ({
    execution_points: (task.execution_points ?? []).join("\n"),
    cautions: (task.cautions ?? []).join("\n"),
    prerequisites: (task.prerequisites ?? []).join("\n"),
  }))
}

function syncPlannerTaskDetails() {
  if (!plannerDraft.value) return
  plannerDraft.value.tasks.forEach((task, index) => {
    const text = plannerTaskDetailsText.value[index]
    if (!text) return
    task.execution_points = parseTaskLines(text.execution_points)
    task.cautions = parseTaskLines(text.cautions)
    task.prerequisites = parseTaskLines(text.prerequisites)
  })
}

function plannerTaskLineLimitMessage() {
  for (const [index, text] of plannerTaskDetailsText.value.entries()) {
    const limits = [
      [text.execution_points, 6, "怎么做"],
      [text.cautions, 5, "注意"],
      [text.prerequisites, 4, "开始前需要"],
    ] as const
    for (const [value, max, label] of limits) {
      const lines = parseTaskLines(value)
      if (lines.length > max) return `第 ${index + 1} 项${label}最多填写 ${max} 条。`
      if (lines.some((line) => line.length > 240)) return `第 ${index + 1} 项${label}每条最多 240 字。`
    }
  }
  return ""
}

function setPlannerDraft(draft: AIPlannerDraft, preserveSelectedTask = false) {
  const selectedIndex = plannerSelectedTaskIndex.value
  if (draft.item.deadline) draft.item.deadline = toLocalInput(draft.item.deadline)
  filterIgnoredPlannerSuggestions(draft, plannerIgnoredSuggestionKeys)
  plannerDraft.value = draft
  resetPlannerTaskDetails(draft)
  plannerSelectedTaskIndex.value = preserveSelectedTask && selectedIndex !== null && selectedIndex < draft.tasks.length
    ? selectedIndex
    : null
  plannerNewTaskIndex.value = null
  plannerRefineOpenIndex.value = null
}

function dismissPlannerSuggestion(index: number) {
  if (!plannerDraft.value) return
  ignorePlannerSuggestion(plannerDraft.value, index, plannerIgnoredSuggestionKeys)
}

async function addPlannerSuggestion(suggestion: AIPlannerSuggestionDraft) {
  await refineAIPlan(undefined, plannerSuggestionJoinInstruction(suggestion))
}

async function generateAIPlan() {
  const description = plannerDescription.value.trim()
  if (description.length < 10) {
    error.value = "请先补充一些事项背景，再生成方案。"
    return
  }

  error.value = ""
  plannerGenerating.value = true
  try {
    const result = await api.generateAIPlan({
      description,
      current_event_context: plannerAttachmentContext.value || undefined,
    })
    setPlannerDraft(result.draft)
  } catch (reason) {
    error.value = messageOf(reason)
  } finally {
    plannerGenerating.value = false
  }
}

async function regenerateAIPlan() {
  plannerDraft.value = null
  await generateAIPlan()
}

async function publishAIPlan() {
  const draft = plannerDraft.value
  if (!draft) return
  fieldErrors.value = {}
  if (!draft.item.title.trim()) {
    await showFieldError("planner-item-title", "请填写事项标题", "需要填写事项标题")
    return
  }
  if (!draft.item.deadline) {
    await showFieldError("planner-item-deadline", "请确认事项截止时间", "需要设置事项截止时间")
    return
  }
  const emptyTaskIndex = draft.tasks.findIndex((task) => !task.title.trim())
  if (emptyTaskIndex >= 0) {
    await showFieldError(`planner-task-title-${emptyTaskIndex}`, `请填写第 ${emptyTaskIndex + 1} 项分工标题`, "需要填写标题")
    return
  }
  const lineLimitError = plannerTaskLineLimitMessage()
  if (lineLimitError) {
    await showFieldError("planner-task-details", lineLimitError, lineLimitError)
    return
  }
  syncPlannerTaskDetails()

  error.value = ""
  plannerPublishing.value = true
  try {
    const result = await api.createTaskBatch({
      item: {
        title: draft.item.title.trim(),
        deliverable: draft.item.deliverable.trim(),
        deadline: draft.item.deadline,
      },
      tasks: draft.tasks.map((task) => ({
        title: task.title.trim(),
        deliverable: task.deliverable.trim(),
        execution_points: task.execution_points,
        cautions: task.cautions,
        prerequisites: task.prerequisites,
        owner_claimable: task.owner_claimable,
        collaboration_open: task.collaboration_open,
      })),
    })
    plannerDraft.value = null
    plannerIgnoredSuggestionKeys.clear()
    plannerDescription.value = ""
    plannerAttachments.value = []
    plannerAttachmentMessage.value = ""
    notice.value = `已创建事项和 ${result.tasks.length} 个分工`
    navigateTasks("all")
  } catch (reason) {
    error.value = messageOf(reason)
  } finally {
    plannerPublishing.value = false
  }
}

async function refineAIPlan(index?: number, instructionOverride?: string) {
  const draft = plannerDraft.value
  if (!draft || plannerRefining.value) return
  const instruction = (instructionOverride ?? (index === undefined ? plannerGlobalInstruction.value : plannerRefineInstruction.value)).trim()
  if (!instruction) {
    error.value = "请先写下希望如何调整。"
    return
  }
  if (index === undefined) plannerRefineOpenIndex.value = null
  else plannerRefineOpenIndex.value = index
  const lineLimitError = plannerTaskLineLimitMessage()
  if (lineLimitError) {
    error.value = lineLimitError
    return
  }
  syncPlannerTaskDetails()
  error.value = ""
  plannerRefining.value = true
  try {
    const result = await api.refineAIPlan({
      description: plannerDescription.value.trim(),
      item_title: draft.item.title.trim() || undefined,
      current_event_context: plannerAttachmentContext.value || undefined,
      draft,
      instruction,
      ...(index === undefined ? {} : { scope_task_index: index }),
    })
    setPlannerDraft(result.draft, true)
    plannerGlobalInstruction.value = ""
    plannerRefineInstruction.value = ""
  } catch (reason) {
    error.value = messageOf(reason)
  } finally {
    plannerRefining.value = false
  }
}

async function syncGitHubKnowledge() {
  knowledgeSyncing.value = true
  error.value = ""
  try {
    knowledgeSyncSummary.value = await api.syncGitHubKnowledge()
    await loadKnowledgeDocuments()
  } catch (reason) {
    error.value = messageOf(reason)
  } finally {
    knowledgeSyncing.value = false
  }
}

async function uploadKnowledgeFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  knowledgeUploading.value = true
  error.value = ""
  try {
    await api.uploadKnowledgeDocument(file)
    await loadKnowledgeDocuments()
    notice.value = `已添加资料：${file.name}`
  } catch (reason) {
    error.value = messageOf(reason)
  } finally {
    input.value = ""
    knowledgeUploading.value = false
  }
}

async function removeKnowledgeDocument(document: KnowledgeDocument) {
  if (!window.confirm(`删除知识条目“${document.title}”？`)) return
  error.value = ""
  try {
    await api.deleteKnowledgeDocument(document.id)
    removePlannerCurrentDocument(document.id)
    await loadKnowledgeDocuments()
  } catch (reason) {
    error.value = messageOf(reason)
  }
}

function knowledgeStatusLabel(document: KnowledgeDocument) {
  if (!document.is_active || document.parse_status === "removed") return "已从来源移除"
  const labels = {
    ready: "可检索",
    truncated: "已截断，可检索",
    failed: "解析失败",
    unparseable: "未提取到文字",
    removed: "已从来源移除",
  }
  const label = labels[document.parse_status]
  return document.parse_error ? `${label} · ${document.parse_error}` : label
}

function chooseKnowledgeFile() {
  knowledgeUploadRef.value?.click()
}

async function logout() {
  await api.logout()
  user.value = null
  tasks.value = []
  members.value = []
  taskMembers.value = []
  aiPlannerAvailable.value = false
  plannerDraft.value = null
  plannerIgnoredSuggestionKeys.clear()
  navigate("/login")
}

function handlePopState() {
  const nextPath = window.location.pathname
  if (path.value !== nextPath && (/^\/tasks\/\d+$/.test(path.value) || /^\/tasks\/\d+$/.test(nextPath))) {
    clearFactSuggestions()
    taskProgressDraft.value = ""
    taskCompletionDraft.value = ""
    taskCompletionSync.value = false
  }
  if (window.location.pathname !== path.value) clearItemReview()
  path.value = window.location.pathname
  fieldErrors.value = {}
  error.value = ""
  showAllDetailActivities.value = false
  if (feedback.value?.kind === "error") clearFeedback()
  syncCollaborationRefreshTimer()
  void loadRoute()
}

onMounted(async () => {
  window.addEventListener("popstate", handlePopState)
  window.addEventListener("keydown", handlePlannerDetailKeydown)
  window.addEventListener("focus", handleExecutionRefreshSignal)
  document.addEventListener("visibilitychange", handleExecutionRefreshSignal)
  try {
    await loadCurrentUser()
  } catch (reason) {
    error.value = messageOf(reason)
  }
  await loadRoute()
  syncCollaborationRefreshTimer()
})

onBeforeUnmount(() => {
  window.removeEventListener("popstate", handlePopState)
  window.removeEventListener("keydown", handlePlannerDetailKeydown)
  window.removeEventListener("focus", handleExecutionRefreshSignal)
  document.removeEventListener("visibilitychange", handleExecutionRefreshSignal)
  if (collaborationRefreshTimer !== undefined) window.clearInterval(collaborationRefreshTimer)
  if (feedbackTimer !== undefined) window.clearTimeout(feedbackTimer)
})
</script>

<template>
  <div v-if="feedback" class="toast-layer" aria-label="操作提示">
    <div class="toast-message" :class="`toast-${feedback.kind}`" :role="feedback.kind === 'error' ? 'alert' : 'status'" :aria-live="feedback.kind === 'error' ? 'assertive' : 'polite'">
      <span>{{ feedback.message }}</span>
      <button type="button" aria-label="关闭提示" @click="clearFeedback">×</button>
    </div>
  </div>

  <main v-if="path === '/login'" class="auth-shell">
    <form class="auth-form" @submit.prevent="submitLogin">
      <p class="brand">TARS BASE</p>
      <h1>登录</h1>
      <label>
        邮箱
        <input v-model="loginEmail" type="email" autocomplete="email" required />
      </label>
      <label>
        密码
        <input
          v-model="loginPassword"
          type="password"
          autocomplete="current-password"
          required
        />
      </label>
      <button class="primary" type="submit">登录</button>
    </form>
  </main>

  <main v-else-if="path.startsWith('/invite/')" class="auth-shell">
    <section class="auth-form">
      <p class="brand">TARS BASE</p>
      <template v-if="invitation">
        <h1>设置密码</h1>
        <div class="identity">
          <strong>{{ invitation.name }}</strong>
          <span>{{ invitation.email }}</span>
        </div>
        <form @submit.prevent="submitInvitation">
          <label>
            密码
            <input
              v-model="invitePassword"
              type="password"
              minlength="8"
              maxlength="128"
              autocomplete="new-password"
              required
            />
          </label>
          <label>
            确认密码
            <input
              v-model="invitePasswordConfirm"
              type="password"
              minlength="8"
              maxlength="128"
              autocomplete="new-password"
              required
            />
          </label>
          <button class="primary" type="submit">激活账号</button>
        </form>
      </template>
      <div v-else-if="loading" class="tars-loading tars-loading-auth" role="status" aria-live="polite">
        <div class="tars-loading-mark" aria-hidden="true">
          <span class="tars-loading-block block-a"></span>
          <span class="tars-loading-block block-b"></span>
          <span class="tars-loading-block block-c"></span>
          <span class="tars-loading-block block-d"></span>
        </div>
        <div class="tars-loading-copy">
          <strong>TARS BASE</strong>
          <span>正在验证邀请…</span>
        </div>
      </div>
      <div v-else class="empty auth-empty-state">
        <span class="empty-code">BASE / INVITE</span>
        <h1>无法使用邀请</h1>
        <p>{{ error || "邀请无效或已失效，请联系管理员。" }}</p>
        <button class="secondary" type="button" @click="navigate('/login')">返回登录</button>
      </div>
    </section>
  </main>

  <main v-else class="app-shell">
    <div class="brand-ribbon" aria-hidden="true"></div>

    <aside class="desktop-sidebar" aria-label="主导航">
      <div class="sidebar-brand-block">
        <button class="sidebar-brand" type="button" @click="navigate('/')">TARS BASE</button>
        <span>JILIN UNIVERSITY · TARS-GO</span>
      </div>

      <nav class="sidebar-nav">
        <button :class="{ active: path === '/' }" type="button" @click="navigate('/')">Base</button>
        <button :class="{ active: path.startsWith('/tasks') }" type="button" @click="navigateTasks('mine')">
          任务
        </button>
        <button
          v-if="isAdmin"
          :class="{ active: path === '/team' }"
          type="button"
          @click="navigate('/team')"
        >
          团队
        </button>
        <button :class="{ active: path === '/me' }" type="button" @click="navigate('/me')">
          我的
        </button>
      </nav>

      <div class="sidebar-account">
        <div class="sidebar-user">
          <strong>{{ user?.name }}</strong>
          <span>{{ user ? roleLabels[user.role] : "" }}</span>
        </div>
        <div class="sidebar-user-actions">
          <button type="button" @click="navigate('/me')">个人信息</button>
          <button type="button" @click="logout">退出登录</button>
        </div>
      </div>
    </aside>

    <header class="mobile-topbar">
      <span class="brand">TARS BASE</span>
      <span class="product-label">JLU · TARS-GO</span>
    </header>

    <div v-if="loading" class="page tars-loading-page">
      <div class="tars-loading" role="status" aria-live="polite">
        <div class="tars-loading-mark" aria-hidden="true">
          <span class="tars-loading-block block-a"></span>
          <span class="tars-loading-block block-b"></span>
          <span class="tars-loading-block block-c"></span>
          <span class="tars-loading-block block-d"></span>
        </div>
        <div class="tars-loading-copy">
          <strong>TARS BASE</strong>
          <span>正在加载…</span>
        </div>
      </div>
    </div>

    <div v-else class="page">
      <template v-if="routeNotFound">
        <section class="system-state">
          <span class="system-code">BASE / 404</span>
          <h1>这个路径不属于当前 Base</h1>
          <p>可能是链接已经变化，或者地址输入有误。</p>
          <button class="primary" type="button" @click="navigate('/')">返回 Base</button>
        </section>
      </template>

      <template v-else-if="path === '/'">
        <section class="base-entry">
          <p class="base-kicker">TARS BASE</p>
          <h1>现在要处理什么？</h1>

          <div
            v-if="aiPlannerAvailable"
            class="planner-composer base-composer"
            :class="{ 'is-drag-active': plannerDragActive, 'is-uploading': plannerUploading }"
            @dragenter.prevent="onPlannerDragOver"
            @dragover.prevent="onPlannerDragOver"
            @dragleave="onPlannerDragLeave"
            @drop="onPlannerDrop"
          >
            <textarea
              v-model="plannerDescription"
              maxlength="5000"
              rows="5"
              aria-label="描述一个事项、活动或需要协调的事情"
              placeholder="描述一个事项、活动或需要协调的事情…"
            />
            <div v-if="plannerAttachments.length" class="planner-attachments" aria-label="本次规划附件">
              <span v-for="attachment in plannerAttachments" :key="attachment.id" class="planner-attachment">
                <span class="planner-attachment-icon" aria-hidden="true">↳</span>
                <span class="planner-attachment-name">{{ attachment.filename }}</span>
                <button type="button" :aria-label="`移除 ${attachment.filename}`" @click="removePlannerAttachment(attachment.id)">×</button>
              </span>
            </div>
            <div class="planner-composer-footer">
              <div class="planner-composer-tools">
                <input
                  ref="plannerFileInput"
                  class="visually-hidden"
                  type="file"
                  accept=".md,.txt,.docx,.pdf"
                  multiple
                  @change="onPlannerFilesSelected"
                />
                <button class="planner-add-file" type="button" :disabled="plannerUploading" @click="choosePlannerFiles">
                  {{ plannerUploading ? "正在读取…" : "＋ 添加资料" }}
                </button>
              </div>
              <button
                class="primary planner-generate"
                type="button"
                :disabled="plannerDescription.trim().length < 10 || plannerGenerating || plannerUploading"
                @click="planFromBase"
              >
                {{ plannerGenerating ? "正在规划…" : "规划" }}
              </button>
            </div>
          </div>
          <p v-if="plannerAttachmentMessage" class="planner-composer-message" role="status">{{ plannerAttachmentMessage }}</p>
          <button v-if="isManager" class="base-manual-create" type="button" @click="startNewTask()">或手动创建任务</button>
        </section>

        <button
          v-if="claimableCount"
          class="claimable-link"
          type="button"
          @click="navigateTasks('claimable')"
        >
          <span>还有 {{ claimableCount }} 项待认领 →</span>
        </button>

        <section>
          <div class="section-heading">
            <h2>我现在要处理</h2>
            <span>{{ homeTaskCards.length }} 项</span>
          </div>
          <div v-if="homeTaskCards.length" class="home-task-cards">
            <button
              v-for="task in homeTaskCards"
              :key="task.id"
              class="home-task-card"
              type="button"
              @click="openTaskDetail(task)"
            >
              <span v-if="task.parent_id" class="state">{{ homeRoot(task)?.title || "事项" }}</span>
              <span v-else class="state">事项</span>
              <strong>{{ task.title }}</strong>
              <span v-if="task.parent_id !== null && task.deliverable" class="home-task-deliverable">{{ task.deliverable }}</span>
              <span class="home-task-meta">{{ formatDate(task.deadline) }} · {{ statusLabels[task.status] }}</span>
              <span class="home-task-arrow" aria-hidden="true">›</span>
            </button>
          </div>
          <div v-else class="empty empty-action empty-state">
            <span class="empty-code">BASE / CLEAR</span>
            <h3>当前没有待处理任务</h3>
          </div>
        </section>
      </template>

      <template v-else-if="path === '/ai-planner'">
        <div class="page-title planner-heading">
          <div>
            <h1>AI 规划事项</h1>
            <p v-if="!plannerDraft">描述越具体，生成结果越准确。</p>
          </div>
          <button type="button" @click="navigate('/tasks')">返回任务</button>
        </div>

        <section v-if="!plannerDraft" class="planner-composer-page">
          <div
            class="planner-composer"
            :class="{ 'is-drag-active': plannerDragActive, 'is-uploading': plannerUploading }"
            @dragenter.prevent="onPlannerDragOver"
            @dragover.prevent="onPlannerDragOver"
            @dragleave="onPlannerDragLeave"
            @drop="onPlannerDrop"
          >
            <textarea
              v-model="plannerDescription"
              maxlength="5000"
              rows="7"
              aria-label="描述你准备做的事项"
              placeholder="告诉 TARS 你准备做什么……&#10;例如：10 月 12 日去力旺实验小学参加科技展，帮我把需要安排的事情整理出来。"
            />
            <div v-if="plannerAttachments.length" class="planner-attachments" aria-label="本次规划附件">
              <span v-for="attachment in plannerAttachments" :key="attachment.id" class="planner-attachment">
                <span class="planner-attachment-icon" aria-hidden="true">↳</span>
                <span class="planner-attachment-name">{{ attachment.filename }}</span>
                <button
                  type="button"
                  :aria-label="`移除 ${attachment.filename}`"
                  @click="removePlannerAttachment(attachment.id)"
                >×</button>
              </span>
            </div>
            <div class="planner-composer-footer">
              <div class="planner-composer-tools">
                <input
                  ref="plannerFileInput"
                  class="visually-hidden"
                  type="file"
                  accept=".md,.txt,.docx,.pdf"
                  multiple
                  @change="onPlannerFilesSelected"
                />
                <button class="planner-add-file" type="button" :disabled="plannerUploading" @click="choosePlannerFiles">
                  {{ plannerUploading ? "正在读取…" : "＋ 添加文件" }}
                </button>
                <small>md、txt、docx、pdf</small>
              </div>
              <button
                class="primary planner-generate"
                type="button"
                :disabled="plannerDescription.trim().length < 10 || plannerGenerating || plannerUploading"
                @click="generateAIPlan"
              >
                {{ plannerGenerating ? "正在生成…" : "生成方案" }}
              </button>
            </div>
            <div v-if="plannerDragActive" class="planner-drop-overlay" aria-hidden="true">
              释放以添加到本次规划
            </div>
          </div>
          <p v-if="plannerAttachmentContextTruncated" class="planner-composer-message" role="status">
            附件文字较多，生成时只会使用前段内容。
          </p>
          <p v-if="plannerAttachmentMessage" class="planner-composer-message" role="status">
            {{ plannerAttachmentMessage }}
          </p>
        </section>

        <section v-else-if="plannerDraft" class="planner-result">
          <div class="planner-result-toolbar">
            <button class="planner-back-link" type="button" @click="editPlannerRequest">← 修改原始需求</button>
            <span>AI 草案</span>
          </div>
          <div class="planner-result-layout" :class="{ 'is-detail-open': plannerSelectedTaskIndex !== null }">
            <div class="planner-overview-column">
              <section class="planner-overview-heading" aria-labelledby="planner-item-title">
                <div>
                  <p>事项总览</p>
                  <h1 id="planner-item-title">{{ plannerDraft.item.title || "未命名事项" }}</h1>
                  <span>{{ plannerDraft.tasks.length }} 个执行任务</span>
                </div>
                <button
                  ref="plannerAddTaskButton"
                  class="secondary planner-add-task"
                  type="button"
                  @click="addPlannerTask"
                >＋ 添加任务</button>
              </section>

              <section class="planner-section planner-overview-tasks">
                <div class="form-title">
                  <h2>执行分工 <span class="planner-task-count">· {{ plannerDraft.tasks.length }} 项</span></h2>
                </div>
                <div v-if="plannerDraft.tasks.length" class="planner-task-list">
                  <button
                    v-for="(task, index) in plannerDraft.tasks"
                    :key="index"
                    :data-planner-task-index="index"
                    class="planner-task-summary"
                    type="button"
                    :aria-label="`打开第 ${index + 1} 项详情：${task.title || '未命名任务'}`"
                    :aria-expanded="plannerSelectedTaskIndex === index"
                    @click="openPlannerTaskDetail(index)"
                  >
                    <span class="planner-summary-index">{{ String(index + 1).padStart(2, "0") }}</span>
                    <span class="planner-summary-content">
                      <strong>{{ task.title || "未命名分工" }}</strong>
                      <span v-if="task.deliverable" class="planner-summary-deliverable">{{ task.deliverable }}</span>
                      <span v-if="plannerTaskStatus(task)" class="planner-summary-status">{{ plannerTaskStatus(task) }}</span>
                    </span>
                    <span class="planner-summary-chevron" aria-hidden="true">›</span>
                  </button>
                </div>
                <p v-else class="muted">当前没有分工，可以直接发布事项或添加一项。</p>
              </section>

              <details class="planner-item-edit">
                <summary>事项信息</summary>
                <div class="planner-fields">
                  <label>
                    事项标题
                    <input
                      v-model="plannerDraft.item.title"
                      data-validation-field="planner-item-title"
                      :aria-invalid="Boolean(fieldErrors['planner-item-title'])"
                      maxlength="200"
                      @input="clearFieldError('planner-item-title')"
                    />
                    <small v-if="fieldErrors['planner-item-title']" class="field-error">{{ fieldErrors['planner-item-title'] }}</small>
                  </label>
                  <label>
                    截止时间
                    <input
                      v-model="plannerDraft.item.deadline"
                      data-validation-field="planner-item-deadline"
                      :aria-invalid="Boolean(fieldErrors['planner-item-deadline'])"
                      type="datetime-local"
                      @input="clearFieldError('planner-item-deadline')"
                    />
                    <small v-if="fieldErrors['planner-item-deadline']" class="field-error">{{ fieldErrors['planner-item-deadline'] }}</small>
                  </label>
                </div>
              </details>

              <details class="planner-global-refine">
                <summary>用 AI 调整整体方案</summary>
                <label>
                  想怎样调整？
                  <textarea v-model="plannerGlobalInstruction" rows="2" maxlength="1000" placeholder="例如：把现场展示和技术保障合并，保留必要的交接任务。" />
                </label>
                <button class="secondary" type="button" :disabled="plannerRefining || plannerPublishing" @click="refineAIPlan()">
                  {{ plannerRefining && plannerRefineOpenIndex === null ? "正在调整…" : "调整整体方案" }}
                </button>
              </details>

              <div v-if="plannerDraft.questions.length" class="planner-section planner-questions">
                <h2>需要确认 · {{ plannerDraft.questions.length }}</h2>
                <ul>
                  <li v-for="question in plannerDraft.questions" :key="question">{{ question }}</li>
                </ul>
              </div>

              <div v-if="plannerDraft.suggestions.length" class="planner-section planner-suggestions">
                <h2>可能遗漏 <span class="planner-task-count">· {{ plannerDraft.suggestions.length }}</span></h2>
                <div class="planner-suggestion-list">
                  <article v-for="(suggestion, index) in plannerDraft.suggestions" :key="suggestion.title + '-' + suggestion.reason" class="planner-suggestion">
                    <div>
                      <h3>{{ suggestion.title }}</h3>
                      <p>{{ suggestion.reason }}</p>
                    </div>
                    <div class="planner-suggestion-actions">
                      <button class="text-action" type="button" :disabled="plannerRefining || plannerPublishing" @click="dismissPlannerSuggestion(index)">忽略</button>
                      <button class="secondary" type="button" :disabled="plannerRefining || plannerPublishing" @click="addPlannerSuggestion(suggestion)">加入方案</button>
                    </div>
                  </article>
                </div>
              </div>

              <div class="planner-publish">
                <button class="secondary" type="button" :disabled="plannerGenerating || plannerPublishing" @click="regenerateAIPlan">
                  重新生成
                </button>
                <button class="primary" type="button" :disabled="plannerPublishing" @click="publishAIPlan">
                  {{ plannerPublishing ? "正在创建…" : "确认并创建" }}
                </button>
              </div>
            </div>

            <aside
              v-if="plannerSelectedTask && plannerSelectedTaskIndex !== null"
              class="planner-task-detail"
              :aria-label="`第 ${plannerSelectedTaskIndex + 1} 项任务详情`"
              role="region"
            >
              <header class="planner-task-detail-header">
                <button ref="plannerDetailBackButton" class="planner-detail-back" type="button" @click="closePlannerTaskDetail">← 返回方案</button>
                <div class="planner-detail-heading">
                  <span>{{ String(plannerSelectedTaskIndex + 1).padStart(2, "0") }}</span>
                  <small>任务详情</small>
                </div>
                <button
                  ref="plannerDetailCloseButton"
                  class="planner-detail-close"
                  type="button"
                  aria-label="关闭任务详情"
                  @click="closePlannerTaskDetail"
                >×</button>
              </header>

              <div class="planner-task-detail-body">
                <label class="planner-detail-title-field">
                  任务标题
                  <input
                    ref="plannerDetailTitleInput"
                    v-model="plannerSelectedTask.title"
                    class="planner-task-title"
                    :data-validation-field="`planner-task-title-${plannerSelectedTaskIndex}`"
                    :aria-invalid="Boolean(fieldErrors[`planner-task-title-${plannerSelectedTaskIndex}`])"
                    maxlength="200"
                    aria-label="任务标题"
                    @input="clearFieldError(`planner-task-title-${plannerSelectedTaskIndex}`)"
                  />
                  <small v-if="fieldErrors[`planner-task-title-${plannerSelectedTaskIndex}`]" class="field-error">{{ fieldErrors[`planner-task-title-${plannerSelectedTaskIndex}`] }}</small>
                </label>
                <label class="planner-detail-deliverable">
                  做到什么算完成
                  <textarea v-model="plannerSelectedTask.deliverable" maxlength="5000" rows="3" placeholder="写清楚看到什么结果即可判定完成" />
                </label>

                <section
                  v-if="plannerTaskDetailsText[plannerSelectedTaskIndex] && (parseTaskLines(plannerTaskDetailsText[plannerSelectedTaskIndex].execution_points).length || parseTaskLines(plannerTaskDetailsText[plannerSelectedTaskIndex].cautions).length || plannerEmptyDetailSection === 'execution_points' || plannerEmptyDetailSection === 'cautions')"
                  class="planner-detail-section planner-execution-hints"
                >
                  <h3>执行提示</h3>
                  <label v-if="parseTaskLines(plannerTaskDetailsText[plannerSelectedTaskIndex].execution_points).length || plannerEmptyDetailSection === 'execution_points'" class="planner-detail-subfield">
                    怎么做
                    <textarea
                      v-model="plannerTaskDetailsText[plannerSelectedTaskIndex].execution_points"
                      data-planner-detail-field="execution_points"
                      data-validation-field="planner-execution-points"
                      rows="2"
                      maxlength="1600"
                      aria-label="怎么做，每行一条，最多 6 条"
                      placeholder="写完成责任所需的关键步骤；每行一条"
                    />
                  </label>
                  <button v-else class="planner-add-detail" type="button" @click="openPlannerEmptyDetailSection('execution_points')">＋ 添加怎么做</button>
                  <label v-if="parseTaskLines(plannerTaskDetailsText[plannerSelectedTaskIndex].cautions).length || plannerEmptyDetailSection === 'cautions'" class="planner-detail-subfield">
                    注意
                    <textarea
                      v-model="plannerTaskDetailsText[plannerSelectedTaskIndex].cautions"
                      data-planner-detail-field="cautions"
                      data-validation-field="planner-cautions"
                      rows="2"
                      maxlength="1200"
                      aria-label="注意，每行一条，最多 5 条"
                      placeholder="只写与当前任务直接相关的提醒"
                    />
                  </label>
                  <button v-else class="planner-add-detail" type="button" @click="openPlannerEmptyDetailSection('cautions')">＋ 添加注意</button>
                </section>
                <button v-else class="planner-add-detail" type="button" @click="openPlannerEmptyDetailSection('execution_points')">＋ 添加执行提示</button>

                <section
                  v-if="plannerTaskDetailsText[plannerSelectedTaskIndex] && (parseTaskLines(plannerTaskDetailsText[plannerSelectedTaskIndex].prerequisites).length || plannerEmptyDetailSection === 'prerequisites')"
                  class="planner-detail-section"
                >
                  <h3>开始前需要</h3>
                  <textarea
                    v-model="plannerTaskDetailsText[plannerSelectedTaskIndex].prerequisites"
                    data-planner-detail-field="prerequisites"
                    data-validation-field="planner-prerequisites"
                    rows="2"
                    maxlength="960"
                    aria-label="开始前需要，每行一条，最多 4 条"
                    placeholder="只有缺少时任务就不能合理开始的条件"
                  />
                </section>
                <button v-else class="planner-add-detail" type="button" @click="openPlannerEmptyDetailSection('prerequisites')">＋ 添加开始条件</button>

                <div class="planner-options planner-detail-options">
                  <div class="planner-option">
                    <label class="check-row">
                      <input v-model="plannerSelectedTask.owner_claimable" type="checkbox" />
                      开放负责人认领
                    </label>
                    <small v-if="!plannerSelectedTask.owner_claimable" class="muted">关闭后，确认发布时由你暂代负责人。</small>
                  </div>
                  <label class="check-row">
                    <input v-model="plannerSelectedTask.collaboration_open" type="checkbox" />
                    开放成员自行加入协作
                  </label>
                </div>

                <div class="planner-card-ai">
                  <button class="text-action" type="button" :disabled="plannerRefining" @click="plannerRefineOpenIndex = plannerRefineOpenIndex === plannerSelectedTaskIndex ? null : plannerSelectedTaskIndex; plannerRefineInstruction = ''">
                    {{ plannerRefineOpenIndex === plannerSelectedTaskIndex ? "收起 AI 调整" : "AI 调整" }}
                  </button>
                  <div v-if="plannerRefineOpenIndex === plannerSelectedTaskIndex" class="planner-card-ai-panel">
                    <label>
                      希望这张卡如何调整？
                      <textarea v-model="plannerRefineInstruction" rows="2" maxlength="1000" placeholder="例如：让新人拿到后更容易执行" />
                    </label>
                    <div class="planner-refine-actions">
                      <button class="secondary" type="button" :disabled="plannerRefining" @click="refineAIPlan(plannerSelectedTaskIndex, '补充执行提示')">补充执行提示</button>
                      <button class="secondary" type="button" :disabled="plannerRefining" @click="refineAIPlan(plannerSelectedTaskIndex, '检查容易遗漏的点')">检查遗漏</button>
                      <button class="secondary" type="button" :disabled="plannerRefining" @click="refineAIPlan(plannerSelectedTaskIndex, '简化这张任务卡，保留最必要的信息')">简化</button>
                      <button class="primary" type="button" :disabled="plannerRefining || !plannerRefineInstruction.trim()" @click="refineAIPlan(plannerSelectedTaskIndex)">
                        {{ plannerRefining ? "正在调整…" : "提交调整" }}
                      </button>
                    </div>
                  </div>
                </div>

                <button class="planner-delete-task" type="button" @click="deleteSelectedPlannerTask">删除这项分工</button>
              </div>
            </aside>
          </div>
        </section>
      </template>

      <template v-else-if="taskDetailId !== null && detailTask && detailRoot">
        <div class="page-title execution-detail-heading">
          <div>
            <button class="detail-back" type="button" @click="detailTask.parent_id ? openTaskDetail(detailRoot) : navigateTasks('all')">← 返回</button>
            <span class="state">{{ detailTask.parent_id ? detailRoot.title : "事项执行" }}</span>
            <h1>{{ detailTask.title }}</h1>
          </div>
          <button v-if="isManager" type="button" @click="editTaskFromDetail(detailTask)">编辑</button>
        </div>

        <template v-if="detailTask.parent_id === null">
          <section class="execution-section">
            <div class="execution-meta">
              <span>{{ statusLabels[detailTask.status] }}</span>
              <span>截止 {{ formatDate(detailTask.deadline) }}</span>
              <span>{{ detailTask.owner ? "总负责人 " + detailTask.owner.name : "总负责人待认领" }}</span>
            </div>
          </section>

          <section v-if="detailChildren.length" class="execution-section progress-summary">
            <div class="progress-summary-heading">
              <strong>{{ detailProgress.label }}</strong>
              <span>{{ detailProgress.detail || "所有分工已完成" }}</span>
            </div>
            <div class="progress-track" role="progressbar" :aria-valuenow="detailProgress.done" :aria-valuemax="detailProgress.total" aria-label="事项完成分工数">
              <span :style="{ width: `${Math.round(detailProgress.done / detailProgress.total * 100)}%` }" />
            </div>
            <small v-if="detailProgress.blocked">{{ detailProgress.blocked }} 项等待前置任务</small>
          </section>

          <section class="execution-section">
            <div class="section-heading review-section-heading">
              <div class="review-section-title"><h2>当前信息</h2><span>{{ detailRoot.item_facts.length }} 条</span></div>
            </div>
            <div v-if="detailRoot.item_facts.length" class="fact-list">
              <article v-for="fact in detailRoot.item_facts" :key="fact.id" class="fact-row fact-row-scoped">
                <div class="fact-row-content">
                  <p>{{ fact.content }}</p>
                  <small>{{ factScopeDescription(fact) }}</small>
                </div>
                <div v-if="canManageFactScope && editingFactScopeId === fact.id" class="fact-scope-editor">
                  <label>
                    同步范围
                    <select v-model="editingFactScope">
                      <option value="global">整个事项都需要知道</option>
                      <option value="related">只与部分分工相关</option>
                    </select>
                  </label>
                  <fieldset v-if="editingFactScope === 'related'" class="fact-task-picker">
                    <legend>相关分工</legend>
                    <label v-for="task in detailChildren" :key="task.id" class="check-row">
                      <input v-model="editingFactTaskIds" type="checkbox" :value="task.id" />
                      {{ task.title }}
                    </label>
                  </fieldset>
                  <div class="fact-scope-actions">
                    <button type="button" @click="cancelFactScopeEdit">取消</button>
                    <button class="primary small-action" type="button" :disabled="editingFactScope === 'related' && !editingFactTaskIds.length" @click="saveFactScope(fact.id)">保存范围</button>
                  </div>
                </div>
                <div v-else-if="canManageFactScope" class="fact-row-actions">
                  <button type="button" @click="beginFactScopeEdit(fact)">调整范围</button>
                  <button type="button" @click="removeCurrentFact(fact.id)">移除</button>
                </div>
                <span v-else class="fact-scope-label">{{ fact.scope === 'global' ? '整个事项' : '与你的工作相关' }}</span>
              </article>
            </div>
            <form v-if="canWriteDetailItem" class="scoped-fact-form" @submit.prevent="addCurrentFact">
              <label>
                新增一条当前信息
                <input v-model="itemFactDraft" maxlength="500" placeholder="写下已经确认、后续执行需要知道的内容" />
              </label>
              <label>
                同步范围
                <select :value="itemFactScope" @change="toggleNewFactScope(($event.target as HTMLSelectElement).value as ItemFactScope)">
                  <option value="global">整个事项都需要知道</option>
                  <option value="related">只与部分分工相关</option>
                </select>
              </label>
              <fieldset v-if="itemFactScope === 'related'" class="fact-task-picker">
                <legend>相关分工</legend>
                <label v-for="task in detailChildren" :key="task.id" class="check-row">
                  <input v-model="itemFactRelatedTaskIds" type="checkbox" :value="task.id" />
                  {{ task.title }}
                </label>
              </fieldset>
              <button type="submit" :disabled="!itemFactDraft.trim() || (itemFactScope === 'related' && !itemFactRelatedTaskIds.length)">＋ 添加信息</button>
            </form>
          </section>

          <section class="execution-section">
            <div class="section-heading">
              <h2>执行任务</h2>
              <button v-if="isManager" type="button" @click="startNewTask(detailRoot)">＋ 添加分工</button>
            </div>
            <div v-if="detailChildren.length" class="detail-task-list">
              <button v-for="task in detailChildren" :key="task.id" class="detail-task-card" type="button" @click="openTaskDetail(task)">
                <span class="state">{{ statusLabels[task.status] }}</span>
                <strong>{{ task.title }}</strong>
                <span v-if="task.deliverable">{{ task.deliverable }}</span>
                <small v-if="task.blocked" class="blocked-inline">等待：{{ task.blocked_by.map((dependency) => dependency.title).join("、") }}</small>
                <small>{{ task.owner ? task.owner.name + " 负责" : "待认领" }} · {{ formatDate(task.deadline) }}</small>
                <span class="home-task-arrow" aria-hidden="true">›</span>
              </button>
            </div>
            <div v-else class="empty compact-empty"><p>还没有执行分工。</p></div>
          </section>

          <section class="execution-section">
            <div class="section-heading"><h2>最近进展</h2></div>
            <div v-if="itemActivities.length" class="activity-list">
              <article v-for="activity in visibleDetailActivities" :key="activity.id" class="activity-row">
                <div class="activity-byline">
                  <time>{{ formatDate(activity.created_at) }}</time>
                  <small>{{ activity.author.name }}</small>
                  <span v-if="activity.task_id" class="activity-source">{{ sourceTaskTitle(activity, tasks) }}</span>
                </div>
                <p>{{ activity.content }}</p>
              </article>
            </div>
            <button v-if="detailTaskActivities.length > 5" type="button" class="text-action activity-more" @click="showAllDetailActivities = !showAllDetailActivities">
              {{ showAllDetailActivities ? '收起进展' : `查看全部 ${detailTaskActivities.length} 条进展` }}
            </button>
            <form v-if="canWriteDetailItem" class="activity-entry" @submit.prevent="recordItemActivity">
              <textarea
                v-model="itemActivityDraft"
                :maxlength="itemActivityAddToFacts ? 500 : 2000"
                rows="3"
                placeholder="记录新动态"
              />
              <div class="activity-entry-actions">
                <label class="check-row">
                  <input v-model="itemActivityAddToFacts" type="checkbox" />
                  同时加入当前信息
                </label>
                <label v-if="itemActivityAddToFacts" class="fact-scope-select">
                  同步范围
                  <select :value="itemActivityFactScope" @change="toggleActivityFactScope(($event.target as HTMLSelectElement).value as ItemFactScope)">
                    <option value="global">整个事项都需要知道</option>
                    <option value="related">只与部分分工相关</option>
                  </select>
                </label>
                <button class="primary" type="submit" :disabled="!itemActivityDraft.trim() || (itemActivityAddToFacts && itemActivityFactScope === 'related' && !itemActivityRelatedTaskIds.length)">发布更新</button>
              </div>
              <fieldset v-if="itemActivityAddToFacts && itemActivityFactScope === 'related'" class="fact-task-picker">
                <legend>相关分工</legend>
                <label v-for="task in detailChildren" :key="task.id" class="check-row">
                  <input v-model="itemActivityRelatedTaskIds" type="checkbox" :value="task.id" />
                  {{ task.title }}
                </label>
              </fieldset>
            </form>
          </section>

          <section v-if="aiPlannerAvailable" class="execution-section ai-review-section">
            <div class="section-heading">
              <h2>方案检查</h2>
              <button class="review-trigger" type="button" :disabled="itemReviewLoading" @click="reviewCurrentItemPlan">
                {{ itemReviewLoading ? "正在检查…" : "让 AI 检查方案" }}
              </button>
            </div>
            <section v-if="itemReviewSummary" class="ai-review-panel" aria-live="polite">
              <div class="ai-review-heading">
                <div><span class="eyebrow">AI 检查结果</span><p>{{ itemReviewSummary }}</p></div>
                <span class="ai-review-count">{{ itemReviewSuggestions.length }} 条建议</span>
              </div>
              <p v-if="!itemReviewSuggestions.length" class="ai-review-empty">当前方案暂未发现需要调整的地方</p>
              <article v-for="entry in itemReviewSuggestions" :key="entry.key" class="ai-review-card">
                <div class="ai-review-card-heading">
                  <span class="eyebrow">{{ entry.suggestion.kind === "add_task" ? "新增任务" : "调整现有任务" }}</span>
                  <h3>{{ entry.suggestion.kind === "add_task" ? entry.suggestion.proposed_task.title : detailChildren.find((task) => task.id === entry.suggestion.target_task_id)?.title ?? entry.suggestion.proposed_task.title }}</h3>
                </div>
                <p class="ai-review-reason"><strong>原因</strong>{{ entry.suggestion.reason }}</p>
                <div v-if="entry.suggestion.kind === 'update_task'" class="ai-review-diffs">
                  <div v-for="change in changesForReviewSuggestion(entry.suggestion)" :key="change.field" class="ai-review-diff">
                    <strong>{{ change.label }}</strong><div class="ai-review-values"><p class="ai-review-before">{{ change.before }}</p><span aria-hidden="true">→</span><p>{{ change.after }}</p></div>
                  </div>
                </div>
                <div v-else class="ai-review-proposal">
                  <div v-if="entry.suggestion.proposed_task.deliverable"><strong>做到什么算完成</strong><p>{{ entry.suggestion.proposed_task.deliverable }}</p></div>
                  <div v-for="section in reviewProposalSections" :key="section.field"><template v-if="entry.suggestion.proposed_task[section.field].length"><strong>{{ section.label }}</strong><ul><li v-for="value in entry.suggestion.proposed_task[section.field]" :key="value">{{ value }}</li></ul></template></div>
                </div>
                <div class="ai-review-actions">
                  <button type="button" @click="dismissItemReviewSuggestion(entry.key)">忽略</button>
                  <button v-if="isManager" class="primary small-action" type="button" :disabled="Boolean(itemReviewApplyingKey)" @click="applyItemReviewSuggestion(entry)">{{ itemReviewApplyingKey === entry.key ? "正在应用…" : "应用" }}</button>
                </div>
              </article>
            </section>
          </section>
        </template>

        <template v-else>
          <section class="execution-section">
            <div class="execution-meta">
              <span>{{ statusLabels[detailTask.status] }}</span>
              <span>{{ detailTask.owner ? detailTask.owner.name + " 负责" : "待认领" }}</span>
              <span v-if="detailTask.collaborators.length">协作 {{ detailTask.collaborators.map((member) => member.name).join("、") }}</span>
              <span>截止 {{ formatDate(detailTask.deadline) }}</span>
            </div>
          </section>

          <section class="execution-section shared-scene">
            <div class="section-heading shared-scene-heading">
              <h2>与你当前工作相关的信息</h2>
              <button type="button" class="text-action" @click="openTaskDetail(detailRoot)">查看全部事项信息 →</button>
            </div>
            <div v-if="detailProgress.total" class="shared-progress-line">
              <strong>{{ detailProgress.label }}</strong>
              <span>{{ detailProgress.detail || "所有分工已完成" }}</span>
              <span v-if="detailProgress.blocked">{{ detailProgress.blocked }} 项等待前置任务</span>
            </div>
            <ul v-if="recentItemFacts.length" class="shared-facts-list">
              <li v-for="fact in recentItemFacts" :key="fact.id">
                <span>{{ fact.content }}</span>
                <small>{{ fact.scope === 'global' ? '整个事项' : '相关分工' }}</small>
              </li>
            </ul>
            <p v-else class="muted">暂时还没有新的确认信息。</p>
          </section>

          <section v-if="detailTask.blocked" class="execution-section dependency-state">
            <div class="section-heading"><h2>等待前置任务</h2></div>
            <ul>
              <li v-for="dependency in detailTask.blocked_by" :key="dependency.id">
                <span>{{ dependency.title }}</span>
                <small>{{ dependency.owner ? `${dependency.owner.name} 负责` : "待认领" }} · {{ statusLabels[dependency.status] }}</small>
              </li>
            </ul>
          </section>
          <p v-else-if="detailTask.depends_on_tasks.length" class="dependency-cleared">前置任务已完成 ✓</p>

          <section v-if="detailTask.deliverable" class="execution-section">
            <div class="section-heading"><h2>做到什么算完成</h2></div>
            <p class="execution-description">{{ detailTask.deliverable }}</p>
          </section>

          <section v-for="section in taskDetailSections(detailTask)" :key="section.title" class="execution-section">
            <div class="section-heading"><h2>{{ section.title }}</h2></div>
            <ul class="execution-list"><li v-for="item in section.items" :key="item">{{ item }}</li></ul>
          </section>

          <section v-if="canPublishTaskProgress" class="execution-section progress-entry-section">
            <div class="section-heading"><h2>更新进展</h2></div>
            <form class="progress-entry" @submit.prevent="publishTaskProgress">
              <label for="task-progress-draft">刚刚发生了什么？</label>
              <textarea id="task-progress-draft" v-model="taskProgressDraft" maxlength="2000" rows="3" placeholder="例如：已经联系对方老师，目前等回复。" />
              <button class="primary" type="submit" :disabled="!taskProgressDraft.trim() || taskProgressSaving">
                {{ taskProgressSaving ? "正在发布…" : "发布更新" }}
              </button>
            </form>
          </section>

          <section v-if="factExtractionLoading || factSuggestions.length" class="execution-section fact-suggestions-panel" aria-live="polite">
            <div class="section-heading"><h2>发现可能需要同步的信息</h2></div>
            <p v-if="factExtractionLoading" class="muted">正在整理这次更新中的已确认信息…</p>
            <template v-else>
              <p>AI 只提供建议。请确认内容与同步范围后再发布。</p>
              <article v-for="(suggestion, index) in factSuggestions" :key="`${index}-${suggestion.text}`" class="fact-suggestion-card">
                <label class="fact-suggestion-check">
                  <input v-model="selectedFactSuggestions" type="checkbox" :value="suggestion.text" />
                  <span>{{ suggestion.text }}<small>{{ suggestion.reason }}</small></span>
                </label>
                <label class="fact-scope-select">
                  同步范围
                  <select v-model="suggestion.scope" @change="ensureFactSuggestionTasks(index)">
                    <option value="global">整个事项都需要知道</option>
                    <option value="related">只与部分分工相关</option>
                  </select>
                </label>
                <fieldset v-if="suggestion.scope === 'related'" class="fact-task-picker">
                  <legend>选择相关分工</legend>
                  <label v-for="task in detailChildren" :key="task.id" class="check-row">
                    <input v-model="suggestion.related_task_ids" type="checkbox" :value="task.id" />
                    {{ task.title }}
                  </label>
                </fieldset>
                <div v-if="suggestion.supersedes_fact_id && detailTask.item_facts.some((fact) => fact.id === suggestion.supersedes_fact_id)" class="fact-replacement">
                  <span>这条信息可能更新现有内容</span>
                  <p>{{ detailTask.item_facts.find((fact) => fact.id === suggestion.supersedes_fact_id)?.content }}</p>
                  <span aria-hidden="true">↓</span>
                  <p>{{ suggestion.text }}</p>
                  <label v-if="canManageFactScope" class="check-row">
                    <input v-model="confirmedFactSupersessions" type="checkbox" :value="suggestion.text" />
                    确认后用新信息替代旧信息
                  </label>
                  <small v-if="!canManageFactScope">替代旧信息需要管理者或事项负责人确认。</small>
                </div>
              </article>
              <div class="fact-suggestion-actions">
                <button type="button" @click="dismissFactSuggestions">不需要同步</button>
                <button
                  class="primary"
                  type="button"
                  :disabled="!selectedFactSuggestions.length || factSuggestions.some((suggestion) => selectedFactSuggestions.includes(suggestion.text) && suggestion.scope === 'related' && !suggestion.related_task_ids.length)"
                  @click="addSuggestedFactsToItem"
                >确认同步</button>
              </div>
            </template>
          </section>

          <section v-if="detailTaskActivities.length" class="execution-section">
            <div class="section-heading"><h2>相关进展</h2></div>
            <div class="activity-list">
              <article v-for="activity in visibleDetailActivities" :key="activity.id" class="activity-row">
                <div class="activity-byline">
                  <time>{{ formatDate(activity.created_at) }}</time>
                  <small>{{ activity.author.name }}</small>
                  <span v-if="activity.task_id" class="activity-source">{{ sourceTaskTitle(activity, tasks) }}</span>
                </div>
                <p>{{ activity.content }}</p>
              </article>
            </div>
            <button v-if="detailTaskActivities.length > 5" type="button" class="text-action activity-more" @click="showAllDetailActivities = !showAllDetailActivities">
              {{ showAllDetailActivities ? '收起进展' : `查看全部 ${detailTaskActivities.length} 条进展` }}
            </button>
          </section>

          <section class="execution-section">
            <div class="section-heading"><h2>最终结果</h2></div>
            <template v-if="canEditDetailResult">
              <textarea v-model="taskResultDraft" maxlength="5000" rows="5" placeholder="记录实际完成后得到的结果" />
              <div class="result-actions">
                <button class="primary" type="button" @click="saveTaskResult">保存结果</button>
              </div>
            </template>
            <p v-else-if="detailTask.result" class="execution-description">{{ detailTask.result }}</p>
            <p v-else class="muted">暂未记录执行结果。</p>
          </section>

          <section v-if="canCompleteDetailTask" class="execution-section complete-task-section">
            <div class="section-heading"><h2>完成任务</h2></div>
            <form class="progress-entry" @submit.prevent="completeDetailTask">
              <label for="task-completion-result">最终结果</label>
              <textarea id="task-completion-result" v-model="taskCompletionDraft" maxlength="5000" rows="3" required placeholder="写下最终完成结果" />
              <label class="check-row">
                <input v-model="taskCompletionSync" type="checkbox" />
                将最终确认信息同步给整个事项（最多 500 字）
              </label>
              <button class="primary" type="submit" :disabled="!taskCompletionDraft.trim() || taskCompletionSaving">
                {{ taskCompletionSaving ? "正在完成…" : "完成任务" }}
              </button>
            </form>
          </section>

          <section class="execution-section task-detail-actions">
            <div class="task-actions">
              <button
                v-if="!detailTask.owner && detailTask.owner_claimable && detailTask.status !== 'done'"
                class="primary small-action"
                type="button"
                @click="claimTask(detailTask)"
              >认领负责人</button>
              <button
                v-if="detailTask.owner?.id === user?.id && detailTask.owner_claimable && detailTask.status !== 'done'"
                type="button"
                @click="unclaimTask(detailTask)"
              >取消认领</button>
              <button
                v-if="detailTask.collaboration_open && detailTask.owner?.id !== user?.id && !isCollaborator(detailTask) && detailTask.status !== 'done'"
                type="button"
                @click="joinTask(detailTask)"
              >加入协作</button>
              <button
                v-if="detailTask.collaboration_open && isCollaborator(detailTask) && detailTask.status !== 'done'"
                type="button"
                @click="leaveTask(detailTask)"
              >退出协作</button>
            </div>
            <div v-if="isManager" class="status-actions">
              <button
                v-for="value in (['todo', 'doing', 'done'] as TaskStatus[])"
                :key="value"
                type="button"
                :class="{ active: detailTask.status === value }"
                @click="updateOwnTaskStatus(detailTask, value)"
              >{{ statusLabels[value] }}</button>
            </div>
          </section>
        </template>
      </template>

      <template v-else-if="path === '/tasks'">
        <div class="page-title">
          <h1>任务</h1>
          <div class="page-title-actions">
            <button v-if="aiPlannerAvailable" class="primary" type="button" @click="startAIPlanner">AI 规划任务</button>
            <button v-if="isManager" class="text-action" type="button" @click="startNewTask()">手动创建</button>
          </div>
        </div>

        <div class="view-tabs" role="tablist" aria-label="任务视图">
          <button
            v-for="view in (['mine', 'claimable', 'all'] as TaskView[])"
            :key="view"
            type="button"
            :class="{ active: taskView === view }"
            @click="navigateTasks(view)"
          >
            {{ viewLabels[view] }}
          </button>
        </div>

        <form v-if="isManager && taskFormOpen" class="management-form task-form" @submit.prevent="submitTask">
          <div class="form-title">
            <div>
              <small v-if="parentTask" class="form-context">分工属于：{{ parentTask.title }}</small>
              <h2>{{ editingTaskId ? "修改任务" : parentTaskId ? "添加分工" : "新建事项" }}</h2>
            </div>
            <button type="button" @click="closeTaskForm">关闭</button>
          </div>

          <label>
            要做什么？
            <input
              v-model="taskTitle"
              data-validation-field="task-title"
              :aria-invalid="Boolean(fieldErrors['task-title'])"
              maxlength="200"
              placeholder="例如：现场摄影"
              @input="clearFieldError('task-title')"
            />
            <small v-if="fieldErrors['task-title']" class="field-error">{{ fieldErrors['task-title'] }}</small>
          </label>

          <fieldset>
            <legend>负责人</legend>
            <div class="choice-row">
              <label class="choice-option">
                <input v-model="taskOwnerMode" type="radio" value="assigned" />
                指定负责人
              </label>
              <label class="choice-option">
                <input v-model="taskOwnerMode" type="radio" value="claimable" />
                待认领
              </label>
            </div>
            <select
              v-if="taskOwnerMode === 'assigned'"
              v-model="taskOwnerId"
              data-validation-field="task-owner"
              :aria-invalid="Boolean(fieldErrors['task-owner'])"
              @change="clearFieldError('task-owner')"
            >
              <option v-for="member in ownerOptions" :key="member.id" :value="member.id">
                {{ member.name }}{{ activeMemberIds.has(member.id) ? "" : "（已停用）" }}
              </option>
            </select>
            <small v-if="fieldErrors['task-owner']" class="field-error">{{ fieldErrors['task-owner'] }}</small>
          </fieldset>

          <label>
            截止时间
            <input
              v-model="taskDeadline"
              data-validation-field="task-deadline"
              :aria-invalid="Boolean(fieldErrors['task-deadline'])"
              type="datetime-local"
              @input="clearFieldError('task-deadline')"
            />
            <small v-if="fieldErrors['task-deadline']" class="field-error">{{ fieldErrors['task-deadline'] }}</small>
          </label>

          <details class="advanced-fields">
            <summary>{{ parentTaskId === null ? "协作设置" : "执行说明与协作设置" }}</summary>
            <div class="advanced-grid">
              <label v-if="parentTaskId !== null">
                做到什么算完成
                <textarea
                  v-model="taskDeliverable"
                  maxlength="5000"
                  rows="3"
                  placeholder="写清楚看到什么结果即可判定完成"
                />
              </label>

              <section v-if="parentTaskId !== null" class="task-edit-hints">
                <h3>执行提示</h3>
                <label>
                  怎么做（每行一条，最多 6 条）
                  <textarea v-model="taskExecutionPointsText" data-validation-field="task-execution-points" rows="2" placeholder="写完成责任所需的关键步骤" />
                  <small v-if="fieldErrors['task-execution-points']" class="field-error">{{ fieldErrors['task-execution-points'] }}</small>
                </label>
                <label v-if="taskCautionsText.trim() || taskCautionsOpen">
                  注意（每行一条，最多 5 条）
                  <textarea v-model="taskCautionsText" data-validation-field="task-cautions" rows="2" placeholder="只写与当前任务直接相关的提醒" />
                  <small v-if="fieldErrors['task-cautions']" class="field-error">{{ fieldErrors['task-cautions'] }}</small>
                </label>
                <button v-else class="planner-add-detail" type="button" @click="taskCautionsOpen = true">＋ 添加注意</button>
              </section>

              <section v-if="parentTaskId !== null" class="task-edit-prerequisites">
                <label v-if="taskPrerequisitesText.trim() || taskPrerequisitesOpen">
                  开始前需要（每行一条，最多 4 条）
                  <textarea v-model="taskPrerequisitesText" data-validation-field="task-prerequisites" rows="2" placeholder="只有缺少时任务就不能合理开始的条件" />
                  <small v-if="fieldErrors['task-prerequisites']" class="field-error">{{ fieldErrors['task-prerequisites'] }}</small>
                </label>
                <button v-else class="planner-add-detail" type="button" @click="taskPrerequisitesOpen = true">＋ 添加开始条件</button>
              </section>

              <fieldset v-if="parentTaskId !== null" class="dependency-edit-list">
                <legend>等待哪些分工（可选）</legend>
                <label v-for="dependency in availableDependencyTasks" :key="dependency.id" class="check-row">
                  <input v-model="taskDependencyIds" type="checkbox" :value="dependency.id" />
                  {{ dependency.title }} · {{ statusLabels[dependency.status] }}
                </label>
                <small v-if="!availableDependencyTasks.length" class="muted">同一事项下还没有其他分工。</small>
              </fieldset>

              <fieldset>
                <legend>协作者</legend>
                <label
                  v-for="member in activeMembers.filter((item) => item.id !== taskOwnerId)"
                  :key="member.id"
                  class="check-row"
                >
                  <input v-model="taskCollaboratorIds" type="checkbox" :value="member.id" />
                  {{ member.name }}
                </label>
                <span v-if="activeMembers.length <= 1" class="muted">暂无其他可选成员</span>
              </fieldset>

              <label class="check-row">
                <input v-model="taskCollaborationOpen" type="checkbox" />
                允许成员自行加入 / 退出协作
              </label>

              <label v-if="taskOwnerMode === 'assigned'" class="check-row">
                <input v-model="taskOwnerClaimable" type="checkbox" />
                允许负责人取消后重新开放认领
              </label>

              <label>
                状态
                <select v-model="taskStatus">
                  <option value="todo">待开始</option>
                  <option value="doing">进行中</option>
                  <option value="done">已完成</option>
                </select>
              </label>
            </div>
          </details>

          <button class="primary" type="submit">
            {{ editingTaskId ? "保存修改" : parentTaskId ? "添加分工" : "发布事项" }}
          </button>
        </form>

        <section class="task-board">
          <div v-if="rootTasks.length || orphanTasks.length" class="operation-list">
            <article v-for="task in rootTasks" :key="task.id" class="operation-card">
              <div class="operation-main">
                <span class="state">事项 · {{ statusLabels[task.status] }}</span>
                <button class="task-title-link" type="button" @click="openTaskDetail(task)"><h3>{{ task.title }}</h3></button>
                <small>
                  {{ task.owner ? "总负责人 " + task.owner.name : "总负责人待认领" }}
                  · 截止 {{ formatDate(task.deadline) }}
                </small>
                <small v-if="task.collaborators.length">
                  协作：{{ task.collaborators.map((member) => member.name).join("、") }}
                </small>
              </div>

              <div class="task-actions">
                <button
                  v-if="!task.owner && task.owner_claimable && task.status !== 'done'"
                  class="primary small-action"
                  type="button"
                  @click="claimTask(task)"
                >
                  认领负责人
                </button>
                <button
                  v-if="task.owner?.id === user?.id && task.owner_claimable && task.status !== 'done'"
                  type="button"
                  @click="unclaimTask(task)"
                >
                  取消认领
                </button>
                <button
                  v-if="task.collaboration_open && task.owner?.id !== user?.id && !isCollaborator(task) && task.status !== 'done'"
                  type="button"
                  @click="joinTask(task)"
                >
                  加入协作
                </button>
                <button
                  v-if="task.collaboration_open && isCollaborator(task) && task.status !== 'done'"
                  type="button"
                  @click="leaveTask(task)"
                >
                  退出协作
                </button>
                <button v-if="isManager" type="button" @click="editTask(task)">编辑</button>
              </div>

              <div v-if="isManager" class="status-actions">
                <button
                  v-for="value in (['todo', 'doing', 'done'] as TaskStatus[])"
                  :key="value"
                  type="button"
                  :class="{ active: task.status === value }"
                  @click="updateOwnTaskStatus(task, value)"
                >
                  {{ statusLabels[value] }}
                </button>
              </div>

              <div v-if="childTasks(task.id).length || (isManager && taskView === 'all')" class="work-breakdown">
                <div class="breakdown-heading">
                  <strong>分工</strong>
                  <button v-if="isManager" type="button" @click="startNewTask(task)">＋ 添加分工</button>
                </div>

                <article v-for="child in childTasks(task.id)" :key="child.id" class="child-task">
                  <div>
                    <span class="state">{{ statusLabels[child.status] }}</span>
                    <button class="task-title-link" type="button" @click="openTaskDetail(child)"><h4>{{ child.title }}</h4></button>
                    <p v-if="child.deliverable">{{ child.deliverable }}</p>
                    <small>
                      {{ child.owner ? child.owner.name + " 负责" : "待认领" }}
                      · 截止 {{ formatDate(child.deadline) }}
                      <template v-if="child.collaborators.length">
                        · 协作 {{ child.collaborators.map((member) => member.name).join("、") }}
                      </template>
                    </small>
                  </div>

                  <div class="task-actions">
                    <button
                      v-if="!child.owner && child.owner_claimable && child.status !== 'done'"
                      class="primary small-action"
                      type="button"
                      @click="claimTask(child)"
                    >
                      认领
                    </button>
                    <button
                      v-if="child.owner?.id === user?.id && child.owner_claimable && child.status !== 'done'"
                      type="button"
                      @click="unclaimTask(child)"
                    >
                      取消认领
                    </button>
                    <button
                      v-if="child.collaboration_open && child.owner?.id !== user?.id && !isCollaborator(child) && child.status !== 'done'"
                      type="button"
                      @click="joinTask(child)"
                    >
                      加入协作
                    </button>
                    <button
                      v-if="child.collaboration_open && isCollaborator(child) && child.status !== 'done'"
                      type="button"
                      @click="leaveTask(child)"
                    >
                      退出协作
                    </button>
                    <button v-if="isManager" type="button" @click="editTask(child)">编辑</button>
                  </div>

                  <div v-if="isManager" class="status-actions">
                    <button
                      v-for="value in (['todo', 'doing', 'done'] as TaskStatus[])"
                      :key="value"
                      type="button"
                      :class="{ active: child.status === value }"
                      @click="updateOwnTaskStatus(child, value)"
                    >
                      {{ statusLabels[value] }}
                    </button>
                  </div>
                </article>
              </div>
            </article>

            <article v-for="task in orphanTasks" :key="task.id" class="operation-card orphan-task">
              <div class="operation-main">
                <span class="state">分工 · {{ statusLabels[task.status] }}</span>
                <button class="task-title-link" type="button" @click="openTaskDetail(task)"><h3>{{ task.title }}</h3></button>
                <p v-if="task.deliverable">{{ task.deliverable }}</p>
                <small>
                  {{ task.owner ? task.owner.name + " 负责" : "待认领" }}
                  · 截止 {{ formatDate(task.deadline) }}
                </small>
              </div>
              <div class="task-actions">
                <button
                  v-if="!task.owner && task.owner_claimable && task.status !== 'done'"
                  class="primary small-action"
                  type="button"
                  @click="claimTask(task)"
                >
                  认领负责人
                </button>
                <button
                  v-if="task.owner?.id === user?.id && task.owner_claimable && task.status !== 'done'"
                  type="button"
                  @click="unclaimTask(task)"
                >
                  取消认领
                </button>
                <button
                  v-if="task.collaboration_open && task.owner?.id !== user?.id && !isCollaborator(task) && task.status !== 'done'"
                  type="button"
                  @click="joinTask(task)"
                >
                  加入协作
                </button>
                <button
                  v-if="task.collaboration_open && isCollaborator(task) && task.status !== 'done'"
                  type="button"
                  @click="leaveTask(task)"
                >
                  退出协作
                </button>
                <button v-if="isManager" type="button" @click="editTask(task)">编辑</button>
              </div>
              <div v-if="isManager" class="status-actions">
                <button
                  v-for="value in (['todo', 'doing', 'done'] as TaskStatus[])"
                  :key="value"
                  type="button"
                  :class="{ active: task.status === value }"
                  @click="updateOwnTaskStatus(task, value)"
                >
                  {{ statusLabels[value] }}
                </button>
              </div>
            </article>
          </div>

          <div v-else class="empty empty-action empty-state">
            <span class="empty-code">
              {{ taskView === 'mine' ? 'TASKS / MINE' : taskView === 'claimable' ? 'TASKS / CLAIM' : 'TASKS / ALL' }}
            </span>
            <h3 v-if="taskView === 'mine'">暂时没有你的执行项</h3>
            <h3 v-else-if="taskView === 'claimable'">当前没有待认领项</h3>
            <h3 v-else>运营列表还是空的</h3>
            <p v-if="taskView === 'mine'">目前没有你负责或参与的任务。</p>
            <p v-else-if="taskView === 'claimable'">新的可认领任务出现后，会显示在这里。</p>
            <p v-else>还没有正式发布的运营事项。</p>
            <button v-if="aiPlannerAvailable && taskView === 'all'" class="primary" type="button" @click="startAIPlanner">AI 规划任务</button>
            <button v-if="isManager && taskView === 'all'" class="text-action" type="button" @click="startNewTask()">手动创建</button>
          </div>
        </section>
      </template>

      <template v-else-if="path === '/me'">
        <div class="page-title"><h1>我的</h1></div>
        <section class="profile">
          <strong>{{ user?.name }}</strong>
          <span>{{ user?.email }}</span>
          <small>{{ user ? roleLabels[user.role] : "" }}</small>
        </section>
        <button class="secondary full" type="button" @click="logout">退出登录</button>
      </template>

      <template v-else-if="path === '/team'">
        <div class="page-title">
          <h1>团队</h1>
          <button type="button" @click="navigate('/knowledge')">团队资料</button>
        </div>
        <form class="management-form" @submit.prevent="submitMemberInvite">
          <h2>邀请成员</h2>
          <label>
            姓名
            <input v-model="memberName" maxlength="100" required />
          </label>
          <label>
            邮箱
            <input v-model="memberEmail" type="email" maxlength="255" required />
          </label>
          <label>
            系统权限
            <select v-model="memberRole">
              <option value="member">成员</option>
              <option value="manager">任务管理员</option>
              <option value="admin">管理员</option>
            </select>
          </label>
          <button class="primary" type="submit">创建邀请</button>
        </form>

        <section v-if="latestInvite" class="invite-result">
          <div>
            <strong>{{ latestInvite.member.name }}</strong>
            <span>邀请有效至 {{ formatDate(latestInvite.expires_at) }}</span>
          </div>
          <button class="primary" type="button" @click="copyInvite">复制邀请链接</button>
        </section>

        <section>
          <div class="section-heading"><h2>成员</h2></div>
          <div class="member-list">
            <div v-for="member in members" :key="member.id" class="member-row">
              <div>
                <strong>{{ member.name }}</strong>
                <span>{{ member.email }}</span>
                <small>{{ roleLabels[member.role] }} · {{ member.status }}</small>
              </div>
              <div class="row-actions">
                <button
                  v-if="member.status === 'invited'"
                  type="button"
                  @click="regenerateInvite(member.id)"
                >
                  生成邀请
                </button>
                <button
                  v-if="member.status === 'active' && member.id !== user?.id"
                  class="danger-text"
                  type="button"
                  @click="disableMember(member.id)"
                >
                  停用
                </button>
                <button
                  v-if="member.status === 'disabled'"
                  type="button"
                  @click="enableMember(member.id)"
                >
                  恢复
                </button>
              </div>
            </div>
          </div>
        </section>
      </template>

      <template v-else-if="path === '/knowledge'">
        <div class="page-title">
          <div>
            <h1>团队资料</h1>
            <p>维护 AI 规划会使用的长期资料。</p>
          </div>
          <button type="button" @click="navigate('/team')">返回团队</button>
        </div>
        <section class="knowledge-actions">
          <button class="primary" type="button" :disabled="knowledgeUploading" @click="chooseKnowledgeFile">
            {{ knowledgeUploading ? "正在上传…" : "上传资料" }}
          </button>
          <input ref="knowledgeUploadRef" class="visually-hidden" type="file" accept=".md,.txt,.docx,.pdf" @change="uploadKnowledgeFile" />
          <small>支持 Markdown、TXT、DOCX 和可提取文字的 PDF，单个文件最大 10 MB。</small>
        </section>
        <details class="knowledge-maintenance">
          <summary>高级维护</summary>
          <button type="button" :disabled="knowledgeSyncing" @click="syncGitHubKnowledge">
            {{ knowledgeSyncing ? "正在同步…" : "同步 GitHub 资料" }}
          </button>
        </details>
        <p v-if="knowledgeSyncSummary" class="message success" role="status">
          同步完成：新增 {{ knowledgeSyncSummary.added }}，更新 {{ knowledgeSyncSummary.updated }}，未变化 {{ knowledgeSyncSummary.unchanged }}，失败 {{ knowledgeSyncSummary.failed }}，已移除 {{ knowledgeSyncSummary.removed }}。
        </p>
        <section>
          <div class="section-heading"><h2>来源文件</h2><span>{{ knowledgeDocuments.length }} 条</span></div>
          <div v-if="knowledgeDocuments.length" class="knowledge-list">
            <article v-for="document in knowledgeDocuments" :key="document.id" class="knowledge-row">
              <div>
                <span class="state">{{ document.source_type === 'github' ? 'GitHub' : '上传' }} · {{ knowledgeStatusLabel(document) }}</span>
                <h3>{{ document.display_name }}</h3>
                <small>{{ document.source_type === 'github' ? document.source_name : document.title }}</small>
                <small>更新于 {{ formatDate(document.synced_at) }}</small>
              </div>
              <button class="danger-text" type="button" @click="removeKnowledgeDocument(document)">删除</button>
            </article>
          </div>
          <div v-else class="empty empty-state">
            <span class="empty-code">KNOWLEDGE / EMPTY</span>
            <h3>还没有团队资料</h3>
            <p>可以从 GitHub 同步，或上传一份文档作为知识来源。</p>
          </div>
        </section>
      </template>
    </div>

    <nav
      class="bottom-nav"
      aria-label="主导航"
      :style="{ gridTemplateColumns: `repeat(${isAdmin ? 4 : 3}, 1fr)` }"
    >
      <button :class="{ active: path === '/' }" type="button" @click="navigate('/')">Base</button>
      <button :class="{ active: path.startsWith('/tasks') }" type="button" @click="navigateTasks('mine')">
        任务
      </button>
      <button
        v-if="isAdmin"
        :class="{ active: path === '/team' }"
        type="button"
        @click="navigate('/team')"
      >
        团队
      </button>
      <button :class="{ active: path === '/me' }" type="button" @click="navigate('/me')">我的</button>
    </nav>
  </main>
</template>
