import type {
  AIPlannerAccess,
  AIPlannerDraft,
  InvitationInfo,
  InviteResult,
  Member,
  MemberSummary,
  Role,
  Task,
  TaskBatchPayload,
  TaskBatchResult,
  TaskStatus,
  TaskView,
} from "./types"

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  })
  if (!response.ok) {
    let message = "操作失败"
    try {
      const data = (await response.json()) as { detail?: string }
      if (data.detail) message = data.detail
    } catch {}
    throw new ApiError(response.status, message)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export interface TaskPayload {
  title: string
  deliverable?: string
  owner_id: number | null
  owner_claimable: boolean
  collaborator_ids: number[]
  collaboration_open: boolean
  parent_id?: number | null
  deadline: string
  status: TaskStatus
}

export const api = {
  me: () => request<Member>("/api/auth/me"),
  login: (email: string, password: string) =>
    request<Member>("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  logout: () => request<void>("/api/auth/logout", { method: "POST" }),

  invitation: (token: string) => request<InvitationInfo>(`/api/invitations/${encodeURIComponent(token)}`),
  acceptInvitation: (token: string, password: string) =>
    request<void>(`/api/invitations/${encodeURIComponent(token)}/accept`, {
      method: "POST",
      body: JSON.stringify({ password }),
    }),

  members: () => request<Member[]>("/api/members"),
  inviteMember: (name: string, email: string, role: Role) =>
    request<InviteResult>("/api/members/invite", {
      method: "POST",
      body: JSON.stringify({ name, email, role }),
    }),
  regenerateInvite: (memberId: number) => request<InviteResult>(`/api/members/${memberId}/invite`, { method: "POST" }),
  disableMember: (memberId: number) => request<Member>(`/api/members/${memberId}/disable`, { method: "POST" }),
  enableMember: (memberId: number) => request<Member>(`/api/members/${memberId}/enable`, { method: "POST" }),

  aiPlannerAccess: () => request<AIPlannerAccess>("/api/ai/planner/access"),
  generateAIPlan: (description: string) =>
    request<AIPlannerDraft>("/api/ai/planner", {
      method: "POST",
      body: JSON.stringify({ description }),
    }),

  taskAssignees: () => request<MemberSummary[]>("/api/tasks/assignees"),
  tasks: (scope: TaskView = "mine") => request<Task[]>(`/api/tasks?scope=${scope}`),
  createTask: (payload: TaskPayload) =>
    request<Task>("/api/tasks", { method: "POST", body: JSON.stringify(payload) }),
  createTaskBatch: (payload: TaskBatchPayload) =>
    request<TaskBatchResult>("/api/tasks/batch", { method: "POST", body: JSON.stringify(payload) }),
  updateTask: (taskId: number, payload: Partial<Omit<TaskPayload, "parent_id">>) =>
    request<Task>(`/api/tasks/${taskId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  claimTask: (taskId: number) => request<Task>(`/api/tasks/${taskId}/claim`, { method: "POST" }),
  unclaimTask: (taskId: number) => request<Task>(`/api/tasks/${taskId}/unclaim`, { method: "POST" }),
  joinTask: (taskId: number) => request<Task>(`/api/tasks/${taskId}/collaborators/join`, { method: "POST" }),
  leaveTask: (taskId: number) => request<Task>(`/api/tasks/${taskId}/collaborators/leave`, { method: "POST" }),
}
