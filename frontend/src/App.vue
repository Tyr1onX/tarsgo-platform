<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue"

import { ApiError, api } from "./api"
import type {
  InvitationInfo,
  InviteResult,
  Member,
  MemberSummary,
  Role,
  Task,
  TaskStatus,
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

const memberName = ref("")
const memberEmail = ref("")
const memberRole = ref<Role>("member")

const editingTaskId = ref<number | null>(null)
const taskTitle = ref("")
const taskDeliverable = ref("")
const taskOwnerId = ref<number | null>(null)
const taskCollaboratorIds = ref<number[]>([])
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
const ownerOptions = computed(() => {
  const options = [...activeMembers.value]
  const owner = editingTask.value?.owner
  if (owner && !activeMemberIds.value.has(owner.id)) options.unshift(owner)
  return options
})
const openTasks = computed(() => tasks.value.filter((task) => task.status !== "done"))
const doneTasks = computed(() => tasks.value.filter((task) => task.status === "done"))
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

function messageOf(reason: unknown): string {
  return reason instanceof Error ? reason.message : "操作失败"
}

function navigate(nextPath: string) {
  if (window.location.pathname !== nextPath) {
    window.history.pushState({}, "", nextPath)
  }
  path.value = nextPath
  error.value = ""
  void loadRoute()
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

function resetTaskForm() {
  editingTaskId.value = null
  taskTitle.value = ""
  taskDeliverable.value = ""
  taskOwnerId.value = activeMembers.value[0]?.id ?? null
  taskCollaboratorIds.value = []
  taskDeadline.value = ""
  taskStatus.value = "todo"
}

function editTask(task: Task) {
  editingTaskId.value = task.id
  taskTitle.value = task.title
  taskDeliverable.value = task.deliverable
  taskOwnerId.value = task.owner.id
  taskCollaboratorIds.value = task.collaborators
    .filter((member) => activeMemberIds.value.has(member.id))
    .map((member) => member.id)
  taskDeadline.value = toLocalInput(task.deadline)
  taskStatus.value = task.status
  window.scrollTo({ top: 0, behavior: "smooth" })
}

function sameIds(left: number[], right: number[]) {
  const sortedLeft = [...left].sort((a, b) => a - b)
  const sortedRight = [...right].sort((a, b) => a - b)
  return sortedLeft.length === sortedRight.length && sortedLeft.every((id, index) => id === sortedRight[index])
}

async function loadCurrentUser() {
  try {
    user.value = await api.me()
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
    } else if (path.value === "/" || path.value === "/tasks") {
      tasks.value = await api.tasks("mine")
    } else if (path.value === "/me") {
      // Current user data is already sufficient.
    } else if (path.value === "/admin/members") {
      if (!isAdmin.value) {
        navigate("/")
        return
      }
      members.value = await api.members()
    } else if (path.value === "/admin/tasks") {
      if (!isManager.value) {
        navigate("/")
        return
      }
      ;[taskMembers.value, tasks.value] = await Promise.all([
        api.taskAssignees(),
        api.tasks("all"),
      ])
      if (!taskOwnerId.value) taskOwnerId.value = activeMembers.value[0]?.id ?? null
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
  if (!taskOwnerId.value || !taskDeadline.value) {
    error.value = "请选择负责人和截止时间"
    return
  }

  try {
    if (editingTaskId.value) {
      const original = editingTask.value
      if (!original) return

      const payload: Parameters<typeof api.updateTask>[1] = {}
      if (taskTitle.value !== original.title) payload.title = taskTitle.value
      if (taskDeliverable.value !== original.deliverable) {
        payload.deliverable = taskDeliverable.value
      }
      if (taskOwnerId.value !== original.owner.id) payload.owner_id = taskOwnerId.value
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
        title: taskTitle.value,
        deliverable: taskDeliverable.value,
        owner_id: taskOwnerId.value,
        collaborator_ids: taskCollaboratorIds.value,
        deadline: taskDeadline.value,
        status: taskStatus.value,
      })
    }
    tasks.value = await api.tasks("all")
    resetTaskForm()
  } catch (reason) {
    error.value = messageOf(reason)
  }
}

async function updateOwnTaskStatus(task: Task, status: TaskStatus) {
  error.value = ""
  try {
    const updated = await api.updateTask(task.id, { status })
    const index = tasks.value.findIndex((item) => item.id === task.id)
    if (index >= 0) tasks.value[index] = updated
  } catch (reason) {
    error.value = messageOf(reason)
  }
}

async function logout() {
  await api.logout()
  user.value = null
  tasks.value = []
  members.value = []
  taskMembers.value = []
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
      <p class="brand">TARS-GO</p>
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
      <p class="brand">TARS-GO</p>
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
      <p v-else-if="loading">正在验证邀请…</p>
      <div v-else class="empty">
        <h1>无法使用邀请</h1>
        <p>{{ error || "邀请无效或已失效，请联系管理员。" }}</p>
      </div>
    </section>
  </main>

  <main v-else class="app-shell">
    <header class="topbar">
      <button
        v-if="path.startsWith('/admin/')"
        class="text-button"
        type="button"
        @click="navigate('/me')"
      >
        返回
      </button>
      <span v-else class="brand">TARS-GO</span>
      <strong v-if="path === '/admin/members'">成员</strong>
      <strong v-else-if="path === '/admin/tasks'">任务管理</strong>
    </header>

    <div v-if="loading" class="page"><p>正在加载…</p></div>

    <div v-else class="page">
      <p v-if="error" class="message error">{{ error }}</p>
      <p v-if="notice" class="message success">{{ notice }}</p>

      <template v-if="path === '/'">
        <section class="hero">
          <p>你好，{{ user?.name }}</p>
          <h1>我现在需要做什么</h1>
        </section>

        <section>
          <div class="section-heading">
            <h2>我的任务</h2>
            <span>{{ openTasks.length }} 项未完成</span>
          </div>
          <div v-if="openTasks.length" class="list">
            <article v-for="task in openTasks" :key="task.id" class="task-row">
              <div>
                <span class="state">{{ statusLabels[task.status] }}</span>
                <h3>{{ task.title }}</h3>
                <p>{{ task.deliverable }}</p>
                <small>截止 {{ formatDate(task.deadline) }} · 负责人 {{ task.owner.name }}</small>
              </div>
            </article>
          </div>
          <p v-else class="empty">当前没有待处理任务。</p>
        </section>

        <section v-if="upcomingTasks.length">
          <div class="section-heading">
            <h2>近期截止</h2>
          </div>
          <div class="compact-list">
            <button
              v-for="task in upcomingTasks"
              :key="task.id"
              type="button"
              @click="navigate('/tasks')"
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

      <template v-else-if="path === '/tasks'">
        <div class="page-title">
          <h1>任务</h1>
        </div>
        <div v-if="tasks.length" class="list">
          <article v-for="task in tasks" :key="task.id" class="task-row">
            <div class="task-main">
              <span class="state">{{ statusLabels[task.status] }}</span>
              <h3>{{ task.title }}</h3>
              <p>{{ task.deliverable }}</p>
              <small>
                截止 {{ formatDate(task.deadline) }} · 负责人 {{ task.owner.name }}
                <template v-if="task.collaborators.length">
                  · 协作 {{ task.collaborators.map((member) => member.name).join("、") }}
                </template>
              </small>
            </div>
            <div v-if="task.owner.id === user?.id" class="status-actions">
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
        <p v-else class="empty">没有与你相关的任务。</p>
      </template>

      <template v-else-if="path === '/me'">
        <div class="page-title">
          <h1>我的</h1>
        </div>
        <section class="profile">
          <strong>{{ user?.name }}</strong>
          <span>{{ user?.email }}</span>
          <small>{{ user ? roleLabels[user.role] : "" }}</small>
        </section>
        <section v-if="isManager" class="management-links">
          <button v-if="isAdmin" type="button" @click="navigate('/admin/members')">
            <span>成员</span>
            <span>›</span>
          </button>
          <button type="button" @click="navigate('/admin/tasks')">
            <span>任务</span>
            <span>›</span>
          </button>
        </section>
        <button class="secondary full" type="button" @click="logout">退出登录</button>
      </template>

      <template v-else-if="path === '/admin/members'">
        <form class="management-form" @submit.prevent="submitMemberInvite">
          <h1>创建成员</h1>
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

      <template v-else-if="path === '/admin/tasks'">
        <form class="management-form" @submit.prevent="submitTask">
          <div class="form-title">
            <h1>{{ editingTaskId ? "修改任务" : "创建任务" }}</h1>
            <button v-if="editingTaskId" type="button" @click="resetTaskForm">取消修改</button>
          </div>
          <label>
            任务
            <input v-model="taskTitle" maxlength="200" required />
          </label>
          <label>
            最终交付
            <textarea v-model="taskDeliverable" maxlength="5000" rows="4" required />
          </label>
          <label>
            负责人
            <select v-model="taskOwnerId" required>
              <option v-for="member in ownerOptions" :key="member.id" :value="member.id">
                {{ member.name }}{{ activeMemberIds.has(member.id) ? "" : "（已停用）" }}
              </option>
            </select>
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
          <label>
            截止时间
            <input v-model="taskDeadline" type="datetime-local" required />
          </label>
          <label>
            状态
            <select v-model="taskStatus">
              <option value="todo">待开始</option>
              <option value="doing">进行中</option>
              <option value="done">已完成</option>
            </select>
          </label>
          <button class="primary" type="submit">
            {{ editingTaskId ? "保存修改" : "创建任务" }}
          </button>
        </form>

        <section>
          <div class="section-heading"><h2>全部任务</h2></div>
          <div v-if="tasks.length" class="list">
            <article v-for="task in tasks" :key="task.id" class="task-row editable">
              <div>
                <span class="state">{{ statusLabels[task.status] }}</span>
                <h3>{{ task.title }}</h3>
                <p>{{ task.deliverable }}</p>
                <small>截止 {{ formatDate(task.deadline) }} · 负责人 {{ task.owner.name }}</small>
              </div>
              <button type="button" @click="editTask(task)">修改</button>
            </article>
          </div>
          <p v-else class="empty">还没有任务。</p>
        </section>
      </template>
    </div>

    <nav v-if="!path.startsWith('/admin/')" class="bottom-nav" aria-label="主导航">
      <button :class="{ active: path === '/' }" type="button" @click="navigate('/')">首页</button>
      <button
        :class="{ active: path === '/tasks' }"
        type="button"
        @click="navigate('/tasks')"
      >
        任务
      </button>
      <button :class="{ active: path === '/me' }" type="button" @click="navigate('/me')">我的</button>
    </nav>
  </main>
</template>
