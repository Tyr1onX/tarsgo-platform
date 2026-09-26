from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

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
    deliverable: str = Field(min_length=1, max_length=5000)
    owner_id: int
    collaborator_ids: list[int] = Field(default_factory=list)
    deadline: datetime
    status: TaskStatus = "todo"

    @field_validator("title", "deliverable")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("内容不能为空")
        return value


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    deliverable: str | None = Field(default=None, min_length=1, max_length=5000)
    owner_id: int | None = None
    collaborator_ids: list[int] | None = None
    deadline: datetime | None = None
    status: TaskStatus | None = None

    @field_validator("title", "deliverable")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("内容不能为空")
        return value


class TaskOut(BaseModel):
    id: int
    title: str
    deliverable: str
    owner: MemberSummary
    collaborators: list[MemberSummary]
    deadline: datetime
    status: TaskStatus
    created_by: int
    created_at: datetime
