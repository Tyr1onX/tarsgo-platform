from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Role = Literal["admin", "manager", "member"]
MemberStatus = Literal["invited", "active", "disabled"]
TaskStatus = Literal["todo", "doing", "done"]


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

    @model_validator(mode="after")
    def validate_owner(self):
        if self.owner_id is None and not self.owner_claimable:
            raise ValueError("任务必须指定负责人或开放负责人认领")
        return self


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    deliverable: str | None = Field(default=None, max_length=5000)
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


class TaskOut(BaseModel):
    id: int
    parent_id: int | None
    title: str
    deliverable: str
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

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 10:
            raise ValueError("请再补充一些事项背景")
        return value


class AIPlannerItemDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    deliverable: str = Field(max_length=1000)
    deadline: datetime | None

    @field_validator("title", "deliverable")
    @classmethod
    def strip_item_text(cls, value: str) -> str:
        return value.strip()


class AIPlannerTaskDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    deliverable: str = Field(max_length=1000)
    owner_claimable: bool
    collaboration_open: bool

    @field_validator("title", "deliverable")
    @classmethod
    def strip_task_text(cls, value: str) -> str:
        return value.strip()


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


class AIPlannerAccessOut(BaseModel):
    available: bool


class TaskBatchItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    deliverable: str = Field(default="", max_length=5000)
    deadline: datetime

    @field_validator("title", "deliverable")
    @classmethod
    def strip_batch_item_text(cls, value: str) -> str:
        return value.strip()


class TaskBatchChildIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    deliverable: str = Field(default="", max_length=5000)
    owner_claimable: bool = True
    collaboration_open: bool = False

    @field_validator("title", "deliverable")
    @classmethod
    def strip_batch_child_text(cls, value: str) -> str:
        return value.strip()


class TaskBatchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item: TaskBatchItemIn
    tasks: list[TaskBatchChildIn] = Field(default_factory=list, max_length=15)


class TaskBatchOut(BaseModel):
    item: TaskOut
    tasks: list[TaskOut]
