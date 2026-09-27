<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue"

import { ApiError, api } from "./api"
import type {
  AIPlannerDraft,
  AIPlannerTaskDraft,
  InvitationInfo,
  InviteResult,
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
const error = ref("")
const notice = ref("")

const loginEmail = ref("")
const loginPassword = ref("")

const invitation = ref<InvitationInfo | null>(null)
const invitePassword = ref("")
const invitePasswordConfirm = ref("")

const tasks = ref<Task[]>([])
const members = ref<Member[]>([])
const taskMembers = ref<MemberSummary[]>([])
const latestInvite = ref<InviteResult | null>(null)
const taskView = ref<TaskView>("mine")
const claimableCount = ref(0)
const aiPlannerAvailable = ref(false)
const plannerDescription = ref("")
const plannerDraft = ref<AIPlannerDraft | null>(null)
const plannerGenerating = ref(false)
const plannerPublishing = ref(false)

const memberName = ref("")
const memberEmail = ref("")
const memberRole = ref<Role>("member")

const taskFormOpen = ref(false)
const editingTaskId = ref<number | null>(null)
const parentTaskId = ref<number | null>(null)
const taskTitle = ref("")
const taskDeliverable = ref("")
const taskOwnerMode = ref<"assigned" | "claimable">("assigned")
const taskOwnerId = ref<number | null>(null)
const taskOwnerClaimable = ref(false)
const taskCollaboratorIds = ref<number[]>([])
const taskCollaborationOpen = ref(false)
const taskDeadline = ref("")
const taskStatus = ref<TaskStatus>("todo")

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
const parentTask = computed(
  () => tasks.value.find((task) => task.id === parentTaskId.value) ?? null,
)
const ownerOptions = computed(() => {
  const options = [...activeMembers.value]
  const owner = editingTask.value?.owner
  if (owner && !activeMemberIds.value.has(owner.id)) options.unshift(owner)
  return options
})
const openTasks = computed(() => tasks.value.filter((task) => task.status !== "done"))
const doneTasks = computed(() => tasks.value.filter((task) => task.status === "done"))
const rootTasks = computed(() => tasks.value.filter((task) => task.parent_id === null))
const loadedTaskIds = computed(() => new Set(tasks.value.map((task) => task.id)))
const orphanTasks = computed(() =>
  tasks.value.filter(
    (task) => task.parent_id !== null && !loadedTaskIds.value.has(task.parent_id),
  ),
)
const upcomingTasks = computed(() => {
  const now = Date.now()
  const limit = now + 7 * 24 * 60 * 60 * 1000
  return openTasks.value.filter((task) => {
    const deadline = new Date(task.deadline).getTime()
    return deadline >= now && deadline <= limit
  })
})

const statusLabels: Record<TaskStatus, string> = {
  todo: "待开始",
  doing: "进行中",
  done: "已完成",
}

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

function navigate(nextPath: string) {
  if (window.location.pathname + window.location.search !== nextPath) {
    window.history.pushState({}, "", nextPath)
  }
  path.value = window.location.pathname
  error.value = ""
  void loadRoute()
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

function isCollaborator(task: Task) {
  return task.collaborators.some((member) => member.id === user.value?.id)
}

function resetTaskForm() {
  editingTaskId.value = null
  parentTaskId.value = null
  taskTitle.value = ""
  taskDeliverable.value = ""
  taskOwnerMode.value = "assigned"
  taskOwnerId.value = activeMembers.value[0]?.id ?? null
  taskOwnerClaimable.value = false
  taskCollaboratorIds.value = []
  taskCollaborationOpen.value = false
  taskDeadline.value = ""
  taskStatus.value = "todo"
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
  taskOwnerMode.value = task.owner ? "assigned" : "claimable"
  taskOwnerId.value = task.owner?.id ?? activeMembers.value[0]?.id ?? null
  taskOwnerClaimable.value = task.owner_claimable
  taskCollaboratorIds.value = task.collaborators
    .filter((member) => activeMemberIds.value.has(member.id))
    .map((member) => member.id)
  taskCollaborationOpen.value = task.collaboration_open
  taskDeadline.value = toLocalInput(task.deadline)
  taskStatus.value = task.status
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
      const [mine, claimable] = await Promise.all([
        api.tasks("mine"),
        api.tasks("claimable"),
      ])
      tasks.value = mine
      claimableCount.value = claimable.length
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
    } else if (path.value === "/team") {
      if (!isAdmin.value) {
        navigate("/")
        return
      }
      members.value = await api.members()
    } else if (path.value === "/me") {
      // Current user data is already sufficient.
    } else {
      navigate("/")
      return
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
  const desiredOwnerId = taskOwnerMode.value === "assigned" ? taskOwnerId.value : null
  const desiredOwnerClaimable =
    taskOwnerMode.value === "claimable" ? true : taskOwnerClaimable.value

  if (!taskDeadline.value) {
    error.value = "请选择截止时间"
    return
  }
  if (taskOwnerMode.value === "assigned" && !desiredOwnerId) {
    error.value = "请选择负责人"
    return
  }

  try {
    if (editingTaskId.value) {
      const original = editingTask.value
      if (!original) return

      const payload: Parameters<typeof api.updateTask>[1] = {}
      if (taskTitle.value !== original.title) payload.title = taskTitle.value
      if (taskDeliverable.value !== original.deliverable) payload.deliverable = taskDeliverable.value
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
        owner_id: desiredOwnerId,
        owner_claimable: desiredOwnerClaimable,
        collaborator_ids: taskCollaboratorIds.value,
        collaboration_open: taskCollaborationOpen.value,
        deadline: taskDeadline.value,
        status: taskStatus.value,
      })
    }

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
    await loadRoute()
  } catch (reason) {
    error.value = messageOf(reason)
  }
}

async function claimTask(task: Task) {
  error.value = ""
  try {
    await api.claimTask(task.id)
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
    await loadRoute()
  } catch (reason) {
    error.value = messageOf(reason)
  }
}

async function joinTask(task: Task) {
  error.value = ""
  try {
    await api.joinTask(task.id)
    await loadRoute()
  } catch (reason) {
    error.value = messageOf(reason)
  }
}

async function leaveTask(task: Task) {
  error.value = ""
  try {
    await api.leaveTask(task.id)
    await loadRoute()
  } catch (reason) {
    error.value = messageOf(reason)
  }
}


function startAIPlanner() {
  error.value = ""
  navigate("/ai-planner")
}

function newPlannerTask(): AIPlannerTaskDraft {
  return {
    title: "",
    deliverable: "",
    owner_claimable: true,
    collaboration_open: false,
  }
}

function addPlannerTask() {
  plannerDraft.value?.tasks.push(newPlannerTask())
}

function removePlannerTask(index: number) {
  plannerDraft.value?.tasks.splice(index, 1)
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
    const draft = await api.generateAIPlan(description)
    if (draft.item.deadline) draft.item.deadline = toLocalInput(draft.item.deadline)
    plannerDraft.value = draft
  } catch (reason) {
    error.value = messageOf(reason)
  } finally {
    plannerGenerating.value = false
  }
}

async function publishAIPlan() {
  const draft = plannerDraft.value
  if (!draft) return
  if (!draft.item.title.trim()) {
    error.value = "请填写事项标题。"
    return
  }
  if (!draft.item.deadline) {
    error.value = "请确认事项截止时间。"
    return
  }
  if (draft.tasks.some((task) => !task.title.trim())) {
    error.value = "每个分工都需要填写标题。"
    return
  }

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
        owner_claimable: task.owner_claimable,
        collaboration_open: task.collaboration_open,
      })),
    })
    plannerDraft.value = null
    plannerDescription.value = ""
    notice.value = `已创建事项和 ${result.tasks.length} 个分工`
    navigateTasks("all")
  } catch (reason) {
    error.value = messageOf(reason)
  } finally {
    plannerPublishing.value = false
  }
}

async function logout() {
  await api.logout()
  user.value = null
  tasks.value = []
  members.value = []
  taskMembers.value = []
  aiPlannerAvailable.value = false
  plannerDraft.value = null
  navigate("/login")
}

function handlePopState() {
  path.value = window.location.pathname
  void loadRoute()
}

onMounted(async () => {
  window.addEventListener("popstate", handlePopState)
  try {
    await loadCurrentUser()
  } catch (reason) {
    error.value = messageOf(reason)
  }
  await loadRoute()
})

onBeforeUnmount(() => window.removeEventListener("popstate", handlePopState))
</script>

<template>
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
      <p v-if="error" class="message error">{{ error }}</p>
      <p v-if="notice" class="message success">{{ notice }}</p>
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
          <p v-if="error" class="message error">{{ error }}</p>
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
      <div v-else class="empty">
        <h1>无法使用邀请</h1>
        <p>{{ error || "邀请无效或已失效，请联系管理员。" }}</p>
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
        <button :class="{ active: path === '/tasks' }" type="button" @click="navigateTasks('mine')">
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
      <p v-if="error" class="message error">{{ error }}</p>
      <p v-if="notice" class="message success">{{ notice }}</p>

      <template v-if="path === '/'">
        <section class="hero">
          <p>BASE / OVERVIEW · 你好，{{ user?.name }}</p>
          <h1>我现在需要做什么</h1>
          <div class="hero-actions">
            <button v-if="isManager" class="hero-action" type="button" @click="startNewTask()">
              ＋ 新建事项
            </button>
            <button v-if="aiPlannerAvailable" class="hero-action" type="button" @click="startAIPlanner">
              AI 帮我规划
            </button>
          </div>
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
            <h2>我的事项</h2>
            <span>{{ openTasks.length }} 项待处理</span>
          </div>
          <div v-if="openTasks.length" class="list">
            <article v-for="task in openTasks" :key="task.id" class="task-row">
              <div>
                <span class="state">{{ task.parent_id ? "分工" : "事项" }} · {{ statusLabels[task.status] }}</span>
                <h3>{{ task.title }}</h3>
                <p v-if="task.deliverable">{{ task.deliverable }}</p>
                <small>
                  {{ task.owner ? task.owner.name + " 负责" : "待认领" }}
                  · 截止 {{ formatDate(task.deadline) }}
                  <template v-if="task.collaborators.length">
                    · 协作 {{ task.collaborators.map((member) => member.name).join("、") }}
                  </template>
                </small>
              </div>
            </article>
          </div>
          <div v-else class="empty empty-action">
            <p>目前没有你负责或协作的未完成事项。</p>
          </div>
        </section>

        <section v-if="upcomingTasks.length">
          <div class="section-heading"><h2>近期截止</h2></div>
          <div class="compact-list">
            <button
              v-for="task in upcomingTasks"
              :key="task.id"
              type="button"
              @click="navigateTasks('mine')"
            >
              <span>{{ task.title }}</span>
              <small>{{ formatDate(task.deadline) }}</small>
            </button>
          </div>
        </section>

        <details v-if="doneTasks.length" class="done-section">
          <summary>已完成 {{ doneTasks.length }} 项</summary>
          <div class="compact-list">
            <div v-for="task in doneTasks" :key="task.id">
              <span>{{ task.title }}</span>
            </div>
          </div>
        </details>
      </template>


      <template v-else-if="path === '/ai-planner'">
        <div class="page-title planner-heading">
          <div>
            <h1>AI 规划事项</h1>
            <p>把已经明确的活动需求写下来，AI 先整理成可编辑草案，不会自动发布。</p>
          </div>
          <button type="button" @click="navigate('/tasks')">返回任务</button>
        </div>

        <section class="planner-input">
          <label>
            你准备做什么？
            <textarea
              v-model="plannerDescription"
              maxlength="5000"
              rows="8"
              placeholder="例如：10 月 12 日去小学做科技展，需要机器人展示、讲解、直播、摄影、周边发放，活动结束后整理素材。具体人员暂时还没定，之后开放认领。"
            />
          </label>
          <div class="planner-input-actions">
            <button class="primary" type="button" :disabled="plannerGenerating" @click="generateAIPlan">
              {{ plannerGenerating ? "正在生成…" : "生成方案" }}
            </button>
            <button class="text-action" type="button" @click="startNewTask()">手动创建 →</button>
            <small>最多 5000 字；每次生成只请求模型一次。</small>
          </div>
        </section>

        <section v-if="plannerDraft" class="planner-draft">
          <div class="planner-section">
            <div class="section-heading"><h2>事项信息</h2></div>
            <div class="planner-fields">
              <label>
                事项标题
                <input v-model="plannerDraft.item.title" maxlength="200" />
              </label>
              <label>
                完成标准（可选）
                <textarea v-model="plannerDraft.item.deliverable" maxlength="5000" rows="3" />
              </label>
              <label>
                截止时间
                <input v-model="plannerDraft.item.deadline" type="datetime-local" required />
              </label>
            </div>
          </div>

          <div class="planner-section">
            <div class="form-title">
              <div>
                <h2>执行分工</h2>
                <small class="muted">可以修改、删除或继续补充分工。</small>
              </div>
              <button type="button" @click="addPlannerTask">＋ 添加分工</button>
            </div>

            <div v-if="plannerDraft.tasks.length" class="planner-task-list">
              <article v-for="(task, index) in plannerDraft.tasks" :key="index" class="planner-task">
                <div class="planner-task-head">
                  <span>分工 {{ index + 1 }}</span>
                  <button type="button" @click="removePlannerTask(index)">删除</button>
                </div>
                <label>
                  标题
                  <input v-model="task.title" maxlength="200" />
                </label>
                <label>
                  完成标准（可选）
                  <textarea v-model="task.deliverable" maxlength="5000" rows="2" />
                </label>
                <div class="planner-options">
                  <label class="check-row">
                    <input v-model="task.owner_claimable" type="checkbox" />
                    开放负责人认领
                  </label>
                  <small v-if="!task.owner_claimable" class="muted">关闭后，确认发布时由你暂代负责人。</small>
                  <label class="check-row">
                    <input v-model="task.collaboration_open" type="checkbox" />
                    开放成员自行加入协作
                  </label>
                </div>
              </article>
            </div>
            <p v-else class="muted">当前没有分工，可以直接发布事项或手动添加。</p>
          </div>

          <div v-if="plannerDraft.questions.length" class="planner-section planner-questions">
            <h2>需要你确认</h2>
            <ul>
              <li v-for="question in plannerDraft.questions" :key="question">{{ question }}</li>
            </ul>
            <small>这些问题只用于确认草案，不会写入任务数据库。</small>
          </div>

          <div class="planner-publish">
            <button class="secondary" type="button" :disabled="plannerGenerating || plannerPublishing" @click="generateAIPlan">
              重新生成
            </button>
            <button class="primary" type="button" :disabled="plannerPublishing" @click="publishAIPlan">
              {{ plannerPublishing ? "正在创建…" : "确认并创建" }}
            </button>
          </div>
        </section>
      </template>

      <template v-else-if="path === '/tasks'">
        <div class="page-title">
          <h1>任务</h1>
          <div class="page-title-actions">
            <button v-if="aiPlannerAvailable" type="button" @click="startAIPlanner">AI 帮我规划</button>
            <button v-if="isManager" type="button" @click="startNewTask()">新建事项</button>
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
            <input v-model="taskTitle" maxlength="200" required placeholder="例如：现场摄影" />
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
            <select v-if="taskOwnerMode === 'assigned'" v-model="taskOwnerId" required>
              <option v-for="member in ownerOptions" :key="member.id" :value="member.id">
                {{ member.name }}{{ activeMemberIds.has(member.id) ? "" : "（已停用）" }}
              </option>
            </select>
          </fieldset>

          <label>
            截止时间
            <input v-model="taskDeadline" type="datetime-local" required />
          </label>

          <details class="advanced-fields">
            <summary>完成标准与协作设置</summary>
            <div class="advanced-grid">
              <label>
                完成标准（可选）
                <textarea
                  v-model="taskDeliverable"
                  maxlength="5000"
                  rows="3"
                  placeholder="例如：照片原图上传并完成分类"
                />
              </label>

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
                <h3>{{ task.title }}</h3>
                <p v-if="task.deliverable">{{ task.deliverable }}</p>
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

              <div v-if="task.owner?.id === user?.id" class="status-actions">
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
                    <h4>{{ child.title }}</h4>
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

                  <div v-if="child.owner?.id === user?.id" class="status-actions">
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
                <h3>{{ task.title }}</h3>
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
              <div v-if="task.owner?.id === user?.id" class="status-actions">
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

          <div v-else class="empty empty-action">
            <p v-if="taskView === 'mine'">目前没有你负责或参与的任务。</p>
            <p v-else-if="taskView === 'claimable'">当前没有待认领的任务。</p>
            <p v-else>还没有正式发布的运营事项。</p>
            <button v-if="isManager && taskView === 'all'" class="primary" type="button" @click="startNewTask()">
              新建事项
            </button>
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
        <div class="page-title"><h1>团队</h1></div>
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
    </div>

    <nav
      class="bottom-nav"
      aria-label="主导航"
      :style="{ gridTemplateColumns: `repeat(${isAdmin ? 4 : 3}, 1fr)` }"
    >
      <button :class="{ active: path === '/' }" type="button" @click="navigate('/')">Base</button>
      <button :class="{ active: path === '/tasks' }" type="button" @click="navigateTasks('mine')">
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
