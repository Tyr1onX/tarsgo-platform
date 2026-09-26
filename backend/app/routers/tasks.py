from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from ..auth import get_current_member
from ..db import get_db
from ..models import Member, Task
from ..schemas import MemberSummary, TaskCreate, TaskOut, TaskUpdate

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _is_manager(member: Member) -> bool:
    return member.role in {"admin", "manager"}


def _task_query():
    return select(Task).options(selectinload(Task.owner), selectinload(Task.collaborators))


def _task_out(task: Task) -> TaskOut:
    return TaskOut(
        id=task.id,
        title=task.title,
        deliverable=task.deliverable,
        owner=MemberSummary.model_validate(task.owner),
        collaborators=[MemberSummary.model_validate(member) for member in task.collaborators],
        deadline=task.deadline,
        status=task.status,
        created_by=task.created_by,
        created_at=task.created_at,
    )


def _load_active_members(db: Session, member_ids: set[int]) -> dict[int, Member]:
    if not member_ids:
        return {}
    members = {
        member.id: member
        for member in db.scalars(
            select(Member).where(Member.id.in_(member_ids), Member.status == "active")
        )
    }
    if members.keys() != member_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="负责人或协作者不存在或未激活")
    return members


def _get_task(db: Session, task_id: int) -> Task:
    task = db.scalar(_task_query().where(Task.id == task_id))
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return task


@router.get("", response_model=list[TaskOut])
def list_tasks(
    scope: str = Query(default="mine", pattern="^(mine|all)$"),
    current: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> list[TaskOut]:
    query = _task_query()
    if scope == "all":
        if not _is_manager(current):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问全部任务")
    else:
        query = query.where(
            or_(
                Task.owner_id == current.id,
                Task.collaborators.any(Member.id == current.id),
            )
        )

    tasks = db.scalars(query.order_by(Task.deadline.asc(), Task.id.desc())).unique().all()
    return [_task_out(task) for task in tasks]


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreate,
    current: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> TaskOut:
    if not _is_manager(current):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权创建任务")

    ids = set(payload.collaborator_ids)
    ids.add(payload.owner_id)
    members = _load_active_members(db, ids)

    task = Task(
        title=payload.title,
        deliverable=payload.deliverable,
        owner_id=payload.owner_id,
        deadline=payload.deadline,
        status=payload.status,
        created_by=current.id,
    )
    task.collaborators = [
        members[member_id]
        for member_id in dict.fromkeys(payload.collaborator_ids)
        if member_id != payload.owner_id
    ]
    db.add(task)
    db.commit()
    db.expire(task)
    return _task_out(_get_task(db, task.id))


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(
    task_id: int,
    payload: TaskUpdate,
    current: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> TaskOut:
    task = _get_task(db, task_id)
    fields = payload.model_fields_set
    if any(getattr(payload, field) is None for field in fields):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="任务字段不能设为空")

    if not _is_manager(current):
        if task.owner_id != current.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有负责人可以更新任务状态")
        if fields - {"status"} or "status" not in fields:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="普通成员只能更新自己负责任务的状态")
        task.status = payload.status
        db.commit()
        db.expire(task)
        return _task_out(_get_task(db, task.id))

    new_owner_id = payload.owner_id if "owner_id" in fields else task.owner_id
    collaborator_ids = (
        payload.collaborator_ids
        if "collaborator_ids" in fields and payload.collaborator_ids is not None
        else [member.id for member in task.collaborators]
    )
    assignment_ids = set(collaborator_ids)
    assignment_ids.add(new_owner_id)
    members = _load_active_members(db, assignment_ids)

    for field in ("title", "deliverable", "deadline", "status"):
        if field in fields:
            setattr(task, field, getattr(payload, field))
    if "owner_id" in fields:
        task.owner_id = new_owner_id
    if "collaborator_ids" in fields or "owner_id" in fields:
        task.collaborators = [
            members[member_id]
            for member_id in dict.fromkeys(collaborator_ids)
            if member_id != new_owner_id
        ]

    db.commit()
    db.expire(task)
    return _task_out(_get_task(db, task.id))
