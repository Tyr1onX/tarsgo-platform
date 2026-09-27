from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

Role = Literal["admin", "manager", "member"]
MemberStatus = Literal["invited", "active", "disabled"]
TaskStatus = Literal["todo", "doing", "done"]
TaskDetailText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=240)]


def _clean_task_details(values: list[str] | None, *, max_items: int, field_name: str) -> list[str] | None:
    if values is None:
        return None
    result: list[str] = []
    for value in values:
        text = value.strip()
        if not text:
            continue
        if len(text) > 240:
            raise ValueError(f"{field_name}单条内容不能超过 240 字")
        result.append(text)
    if len(result) > max_items:
        raise ValueError(f"{field_name}最多 {max_items} 条")
    return result


def normalize_email(value: str) -> str:
    email = value.strip().lower()
    if len(email) > 255 or "@" not in email or " " in email:
        raise ValueError("请输入有效邮箱")
    local, _, domain = email.partition("@")
    if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
        raise ValueError("请输入有效邮箱")
    return email


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)


class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str
    role: Role
    status: MemberStatus
    created_at: datetime


class InviteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=255)
    role: Role = "member"

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("姓名不能为空")
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)


class InviteOut(BaseModel):
    member: MemberOut
    invite_path: str
    expires_at: datetime


class InvitationInfo(BaseModel):
    name: str
    email: str
    expires_at: datetime


class InvitationAccept(BaseModel):
    password: str = Field(min_length=8, max_length=128)


class MemberSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    deliverable: str = Field(default="", max_length=5000)
    execution_points: list[TaskDetailText] = Field(default_factory=list, max_length=6)
    cautions: list[TaskDetailText] = Field(default_factory=list, max_length=5)
    prerequisites: list[TaskDetailText] = Field(default_factory=list, max_length=4)
    owner_id: int | None = None
    owner_claimable: bool = False
    collaborator_ids: list[int] = Field(default_factory=list)
    collaboration_open: bool = False
    parent_id: int | None = None
    deadline: datetime
    status: TaskStatus = "todo"

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("任务内容不能为空")
        return value

    @field_validator("deliverable")
    @classmethod
    def strip_deliverable(cls, value: str) -> str:
        return value.strip()

    @field_validator("execution_points")
    @classmethod
    def clean_execution_points(cls, value: list[str]) -> list[str]:
        return _clean_task_details(value, max_items=6, field_name="执行要点") or []

    @field_validator("cautions")
    @classmethod
    def clean_cautions(cls, value: list[str]) -> list[str]:
        return _clean_task_details(value, max_items=5, field_name="注意事项") or []

    @field_validator("prerequisites")
    @classmethod
    def clean_prerequisites(cls, value: list[str]) -> list[str]:
        return _clean_task_details(value, max_items=4, field_name="前置条件") or []

    @model_validator(mode="after")
    def validate_owner(self):
        if self.owner_id is None and not self.owner_claimable:
            raise ValueError("任务必须指定负责人或开放负责人认领")
        return self


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    deliverable: str | None = Field(default=None, max_length=5000)
    execution_points: list[TaskDetailText] | None = Field(default=None, max_length=6)
    cautions: list[TaskDetailText] | None = Field(default=None, max_length=5)
    prerequisites: list[TaskDetailText] | None = Field(default=None, max_length=4)
    owner_id: int | None = None
    owner_claimable: bool | None = None
    collaborator_ids: list[int] | None = None
    collaboration_open: bool | None = None
    deadline: datetime | None = None
    status: TaskStatus | None = None

    @field_validator("title")
    @classmethod
    def strip_optional_title(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("任务内容不能为空")
        return value

    @field_validator("deliverable")
    @classmethod
    def strip_optional_deliverable(cls, value: str | None) -> str | None:
        return None if value is None else value.strip()

    @field_validator("execution_points")
    @classmethod
    def clean_optional_execution_points(cls, value: list[str] | None) -> list[str] | None:
        return _clean_task_details(value, max_items=6, field_name="执行要点")

    @field_validator("cautions")
    @classmethod
    def clean_optional_cautions(cls, value: list[str] | None) -> list[str] | None:
        return _clean_task_details(value, max_items=5, field_name="注意事项")

    @field_validator("prerequisites")
    @classmethod
    def clean_optional_prerequisites(cls, value: list[str] | None) -> list[str] | None:
        return _clean_task_details(value, max_items=4, field_name="前置条件")


class TaskOut(BaseModel):
    id: int
    parent_id: int | None
    title: str
    deliverable: str
    execution_points: list[str] = Field(default_factory=list)
    cautions: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    owner: MemberSummary | None
    owner_claimable: bool
    collaborators: list[MemberSummary]
    collaboration_open: bool
    deadline: datetime
    status: TaskStatus
    created_by: int
    created_at: datetime


class AIPlannerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str = Field(min_length=10, max_length=5000)
    item_title: str | None = Field(default=None, max_length=200)
    current_event_context: str | None = Field(default=None, max_length=5000)
    current_event_document_ids: list[int] = Field(default_factory=list, max_length=5)
    excluded_historical_document_ids: list[int] = Field(default_factory=list, max_length=6)

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 10:
            raise ValueError("请再补充一些事项背景")
        return value

    @field_validator("item_title")
    @classmethod
    def strip_item_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("current_event_context")
    @classmethod
    def strip_current_event_context(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("current_event_document_ids")
    @classmethod
    def validate_document_ids(cls, value: list[int]) -> list[int]:
        if any(document_id < 1 for document_id in value) or len(set(value)) != len(value):
            raise ValueError("资料选择无效")
        return value

    @field_validator("excluded_historical_document_ids")
    @classmethod
    def validate_excluded_document_ids(cls, value: list[int]) -> list[int]:
        if any(document_id < 1 for document_id in value) or len(set(value)) != len(value):
            raise ValueError("资料排除项无效")
        return value


class AIPlannerItemDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    deliverable: str = Field(max_length=1000)
    deadline: datetime | None

    @field_validator("title")
    @classmethod
    def strip_item_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("事项标题不能为空")
        return value

    @field_validator("deliverable")
    @classmethod
    def strip_item_deliverable(cls, value: str) -> str:
        return value.strip()


class AIPlannerTaskDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    deliverable: str = Field(max_length=1000)
    execution_points: list[TaskDetailText] = Field(max_length=6)
    cautions: list[TaskDetailText] = Field(max_length=5)
    prerequisites: list[TaskDetailText] = Field(max_length=4)
    owner_claimable: bool
    collaboration_open: bool

    @field_validator("title")
    @classmethod
    def strip_task_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("分工标题不能为空")
        return value

    @field_validator("deliverable")
    @classmethod
    def strip_task_deliverable(cls, value: str) -> str:
        return value.strip()

    @field_validator("execution_points")
    @classmethod
    def clean_execution_points(cls, value: list[str]) -> list[str]:
        return _clean_task_details(value, max_items=6, field_name="执行要点") or []

    @field_validator("cautions")
    @classmethod
    def clean_cautions(cls, value: list[str]) -> list[str]:
        return _clean_task_details(value, max_items=5, field_name="注意事项") or []

    @field_validator("prerequisites")
    @classmethod
    def clean_prerequisites(cls, value: list[str]) -> list[str]:
        return _clean_task_details(value, max_items=4, field_name="前置条件") or []


class AIPlannerDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item: AIPlannerItemDraft
    tasks: list[AIPlannerTaskDraft] = Field(min_length=1, max_length=15)
    questions: list[str] = Field(max_length=6)

    @field_validator("questions")
    @classmethod
    def validate_questions(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            text = value.strip()
            if not text:
                continue
            if len(text) > 200:
                raise ValueError("确认问题过长")
            result.append(text)
        return result


class AIPlannerRefineRequest(AIPlannerRequest):
    model_config = ConfigDict(extra="forbid")
    draft: AIPlannerDraft
    instruction: str = Field(min_length=1, max_length=1000)
    scope_task_index: int | None = Field(default=None, ge=0, le=14)

    @field_validator("instruction")
    @classmethod
    def strip_instruction(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("请输入调整要求")
        return value

    @model_validator(mode="after")
    def validate_refine_draft(self):
        if self.scope_task_index is not None and self.scope_task_index >= len(self.draft.tasks):
            raise ValueError("指定的分工不存在")
        if len(self.draft.model_dump_json()) > 30_000:
            raise ValueError("当前草案过长，请先删减后再调整")
        return self


class AIPlannerAccessOut(BaseModel):
    available: bool


class KnowledgeDocumentOut(BaseModel):
    id: int
    source_type: Literal["github", "upload"]
    source_name: str
    display_name: str
    title: str
    parse_status: Literal["ready", "truncated", "failed", "unparseable", "removed"]
    parse_error: str | None
    is_active: bool
    synced_at: datetime
    source_updated_at: datetime | None


class KnowledgeReferenceOut(BaseModel):
    id: int
    source_type: Literal["github", "upload"]
    source_name: str
    source_label: str
    title: str


class AIPlannerGenerateOut(BaseModel):
    draft: AIPlannerDraft
    current_event_documents: list[KnowledgeReferenceOut] = Field(default_factory=list)
    historical_documents: list[KnowledgeReferenceOut] = Field(default_factory=list)


class AIPlannerExtractOut(BaseModel):
    filename: str
    extracted_text: str
    parse_status: Literal["ready", "truncated", "failed", "unparseable"]
    error: str | None = None


class KnowledgeSyncOut(BaseModel):
    added: int
    updated: int
    unchanged: int
    failed: int
    removed: int


class TaskBatchItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    deliverable: str = Field(default="", max_length=5000)
    deadline: datetime

    @field_validator("title")
    @classmethod
    def strip_batch_item_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("事项标题不能为空")
        return value

    @field_validator("deliverable")
    @classmethod
    def strip_batch_item_deliverable(cls, value: str) -> str:
        return value.strip()


class TaskBatchChildIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    deliverable: str = Field(default="", max_length=5000)
    execution_points: list[TaskDetailText] = Field(default_factory=list, max_length=6)
    cautions: list[TaskDetailText] = Field(default_factory=list, max_length=5)
    prerequisites: list[TaskDetailText] = Field(default_factory=list, max_length=4)
    owner_claimable: bool = True
    collaboration_open: bool = False

    @field_validator("title")
    @classmethod
    def strip_batch_child_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("分工标题不能为空")
        return value

    @field_validator("deliverable")
    @classmethod
    def strip_batch_child_deliverable(cls, value: str) -> str:
        return value.strip()

    @field_validator("execution_points")
    @classmethod
    def clean_execution_points(cls, value: list[str]) -> list[str]:
        return _clean_task_details(value, max_items=6, field_name="执行要点") or []

    @field_validator("cautions")
    @classmethod
    def clean_cautions(cls, value: list[str]) -> list[str]:
        return _clean_task_details(value, max_items=5, field_name="注意事项") or []

    @field_validator("prerequisites")
    @classmethod
    def clean_prerequisites(cls, value: list[str]) -> list[str]:
        return _clean_task_details(value, max_items=4, field_name="前置条件") or []


class TaskBatchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item: TaskBatchItemIn
    tasks: list[TaskBatchChildIn] = Field(default_factory=list, max_length=15)


class TaskBatchOut(BaseModel):
    item: TaskOut
    tasks: list[TaskOut]
