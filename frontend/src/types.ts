export type Role = "admin" | "manager" | "member"
export type MemberStatus = "invited" | "active" | "disabled"
export type TaskStatus = "todo" | "doing" | "done"
export type TaskView = "mine" | "claimable" | "all"
export type ItemFactScope = "global" | "related"

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
  item_facts: ItemFact[]
  context_facts: string[]
  result: string
  owner: MemberSummary | null
  owner_claimable: boolean
  collaborators: MemberSummary[]
  collaboration_open: boolean
  deadline: string | null
  status: TaskStatus
  created_by: number
  created_at: string
  depends_on_tasks: TaskDependency[]
  blocked: boolean
  blocked_by: TaskDependency[]
}

export interface TaskDependency {
  id: number
  title: string
  status: TaskStatus
  owner: MemberSummary | null
}

export interface ItemActivity {
  id: number
  root_task_id: number
  task_id: number | null
  author: MemberSummary
  content: string
  created_at: string
}

export interface ItemActivityPage {
  items: ItemActivity[]
  has_more: boolean
  next_before_id: number | null
}

export interface TaskDetailContext {
  root: Task
  tasks: Task[]
  activity_page: ItemActivityPage
}

export interface ItemFact {
  id: number
  root_task_id: number
  content: string
  scope: ItemFactScope
  related_tasks: Array<{ id: number; title: string }>
  source_activity_id: number | null
  created_by: MemberSummary
  created_at: string
  superseded_by_id: number | null
}

export interface ItemFactInput {
  content: string
  scope: ItemFactScope
  related_task_ids: number[]
  source_activity_id?: number | null
  supersedes_fact_id?: number | null
}

export interface TaskProgressResult {
  task: Task
  activity: ItemActivity
}

export interface AIItemFactSuggestion {
  text: string
  reason: string
  scope: ItemFactScope
  related_task_ids: number[]
  supersedes_fact_id: number | null
}

export interface AIItemFactExtractionResult {
  suggestions: AIItemFactSuggestion[]
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
  deadline: string | null
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
  item: { title: string; deliverable: string; deadline: string | null }
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
export interface AIItemReviewTaskProposal {
  title: string
  deliverable: string
  execution_points: string[]
  cautions: string[]
  prerequisites: string[]
}
export interface AIItemReviewSuggestion {
  kind: "update_task" | "add_task"
  target_task_id: number | null
  reason: string
  proposed_task: AIItemReviewTaskProposal
}
export interface AIItemReviewResult {
  summary: string
  suggestions: AIItemReviewSuggestion[]
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
