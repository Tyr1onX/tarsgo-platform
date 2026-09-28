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
  execution_points: string[]
  cautions: string[]
  prerequisites: string[]
  context_facts: string[]
  result: string
  owner: MemberSummary | null
  owner_claimable: boolean
  collaborators: MemberSummary[]
  collaboration_open: boolean
  deadline: string
  status: TaskStatus
  created_by: number
  created_at: string
}

export interface ItemActivity {
  id: number
  root_task_id: number
  author: MemberSummary
  content: string
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

export interface AIPlannerAccess { available: boolean }
export interface AIPlannerInput {
  description: string
  item_title?: string
  current_event_context?: string
  current_event_document_ids?: number[]
  excluded_historical_document_ids?: number[]
}
export interface AIPlannerItemDraft {
  title: string
  deliverable: string
  deadline: string | null
}
export interface AIPlannerTaskDraft {
  title: string
  deliverable: string
  execution_points: string[]
  cautions: string[]
  prerequisites: string[]
  owner_claimable: boolean
  collaboration_open: boolean
}
export interface AIPlannerSuggestionDraft {
  title: string
  reason: string
}
export interface AIPlannerDraft {
  item: AIPlannerItemDraft
  tasks: AIPlannerTaskDraft[]
  questions: string[]
  suggestions: AIPlannerSuggestionDraft[]
}
export interface AIPlannerRefineInput extends AIPlannerInput {
  draft: AIPlannerDraft
  instruction: string
  scope_task_index?: number
}
export interface TaskBatchPayload {
  item: { title: string; deliverable: string; deadline: string }
  tasks: AIPlannerTaskDraft[]
}
export interface TaskBatchResult {
  item: Task
  tasks: Task[]
}

export type KnowledgeParseStatus = "ready" | "truncated" | "failed" | "unparseable" | "removed"
export interface KnowledgeDocument {
  id: number
  source_type: "github" | "upload"
  source_name: string
  display_name: string
  title: string
  parse_status: KnowledgeParseStatus
  parse_error: string | null
  is_active: boolean
  synced_at: string
  source_updated_at: string | null
}
export interface KnowledgeReference {
  id: number
  source_type: "github" | "upload"
  source_name: string
  source_label: string
  title: string
}
export interface AIPlannerResult {
  draft: AIPlannerDraft
  current_event_documents: KnowledgeReference[]
  historical_documents: KnowledgeReference[]
}
export interface AIPlannerExtractedFile {
  filename: string
  extracted_text: string
  parse_status: "ready" | "truncated" | "failed" | "unparseable"
  error: string | null
}
export interface KnowledgeSyncSummary {
  added: number
  updated: number
  unchanged: number
  failed: number
  removed: number
}