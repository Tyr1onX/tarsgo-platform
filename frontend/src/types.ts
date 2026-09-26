export type Role = "admin" | "manager" | "member"
export type MemberStatus = "invited" | "active" | "disabled"
export type TaskStatus = "todo" | "doing" | "done"
export type TaskView = "mine" | "claimable" | "all"

export interface Member {
  id: number
  name: string
  email: string
  role: Role
  status: MemberStatus
  created_at: string
}

export interface MemberSummary {
  id: number
  name: string
}

export interface Task {
  id: number
  parent_id: number | null
  title: string
  deliverable: string
  owner: MemberSummary | null
  owner_claimable: boolean
  collaborators: MemberSummary[]
  collaboration_open: boolean
  deadline: string
  status: TaskStatus
  created_by: number
  created_at: string
}

export interface InviteResult {
  member: Member
  invite_path: string
  expires_at: string
}

export interface InvitationInfo {
  name: string
  email: string
  expires_at: string
}
