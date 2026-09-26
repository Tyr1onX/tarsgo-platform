from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session, selectinload

from ..auth import get_current_member, require_manager
from ..db import get_db
from ..models import Member, Task, task_collaborators
from ..schemas import MemberSummary, TaskCreate, TaskOut, TaskUpdate

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _is_manager(member: Member) -> bool:
    return member.role in {"admin", "manager"}


def _task_query():
    return select(Task).options(selectinload(Task.owner), selectinload(Task.collaborators))


def _task_out(task: Task) -> TaskOut:
    return TaskOut(
        id=task.id,
        parent_id=task.parent_id,
        title=task.title,
        deliverable=task.deliverable,
        owner=MemberSummary.model_validate(task.owner) if task.owner else None,
        owner_claimable=task.owner_claimable,
        collaborators=[MemberSummary.model_validate(member) for member in task.collaborators],
        collaboration_open=task.collaboration_open,
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="负责人或协作者不存在或未激活",
        )
    return members


def _get_task(db: Session, task_id: int) -> Task:
    task = db.scalar(_task_query().where(Task.id == task_id))
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return task


def _validate_parent(db: Session, parent_id: int | None) -> None:
    if parent_id is None:
        return
    parent = db.get(Task, parent_id)
    if not parent:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="父事项不存在")
    if parent.parent_id is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前阶段只支持一级分工")


def _validate_owner_state(owner_id: int | None, owner_claimable: bool) -> None:
    if owner_id is None and not owner_claimable:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="任务必须指定负责人或开放负责人认领",
        )


@router.get("", response_model=list[TaskOut])
def list_tasks(
    scope: str = Query(default="mine", pattern="^(mine|claimable|all)$"),
    current: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> list[TaskOut]:
    query = _task_query()
    if scope == "mine":
        query = query.where(
            or_(
                Task.owner_id == current.id,
                Task.collaborators.any(Member.id == current.id),
            )
        )
    elif scope == "claimable":
        query = query.where(
            Task.owner_id.is_(None),
            Task.owner_claimable.is_(True),
            Task.status != "done",
        )

    tasks = db.scalars(query.order_by(Task.deadline.asc(), Task.id.asc())).unique().all()
    return [_task_out(task) for task in tasks]


@router.get("/assignees", response_model=list[MemberSummary])
def list_task_assignees(
    _: Member = Depends(require_manager),
    db: Session = Depends(get_db),
) -> list[Member]:
    return list(
        db.scalars(
            select(Member)
            .where(Member.status == "active")
            .order_by(Member.name.asc(), Member.id.asc())
        )
    )


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreate,
    current: Member = Depends(require_manager),
    db: Session = Depends(get_db),
) -> TaskOut:
    _validate_parent(db, payload.parent_id)
    _validate_owner_state(payload.owner_id, payload.owner_claimable)

    member_ids = set(payload.collaborator_ids)
    if payload.owner_id is not None:
        member_ids.add(payload.owner_id)
    members = _load_active_members(db, member_ids)

    task = Task(
        parent_id=payload.parent_id,
        title=payload.title,
        deliverable=payload.deliverable,
        owner_id=payload.owner_id,
        owner_claimable=payload.owner_claimable,
        collaboration_open=payload.collaboration_open,
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

    if not _is_manager(current):
        if task.owner_id != current.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有负责人可以更新任务状态")
        if fields != {"status"} or payload.status is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="普通成员只能更新自己负责任务的状态")
        task.status = payload.status
        db.commit()
        db.expire(task)
        return _task_out(_get_task(db, task.id))

    required_non_null = {
        "title",
        "deliverable",
        "collaborator_ids",
        "owner_claimable",
        "collaboration_open",
        "deadline",
        "status",
    }
    if any(field in fields and getattr(payload, field) is None for field in required_non_null):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="任务字段不能设为空")

    resulting_owner_id = payload.owner_id if "owner_id" in fields else task.owner_id
    resulting_claimable = (
        payload.owner_claimable if "owner_claimable" in fields else task.owner_claimable
    )
    _validate_owner_state(resulting_owner_id, bool(resulting_claimable))

    if "owner_id" in fields and resulting_owner_id is not None:
        _load_active_members(db, {resulting_owner_id})

    for field in (
        "title",
        "deliverable",
        "owner_claimable",
        "collaboration_open",
        "deadline",
        "status",
    ):
        if field in fields:
            setattr(task, field, getattr(payload, field))

    if "owner_id" in fields:
        task.owner_id = resulting_owner_id

    if "collaborator_ids" in fields:
        collaborator_ids = payload.collaborator_ids or []
        members = _load_active_members(db, set(collaborator_ids))
        task.collaborators = [
            members[member_id]
            for member_id in dict.fromkeys(collaborator_ids)
            if member_id != resulting_owner_id
        ]
    elif "owner_id" in fields and resulting_owner_id is not None:
        task.collaborators = [
            member for member in task.collaborators if member.id != resulting_owner_id
        ]

    db.commit()
    db.expire(task)
    return _task_out(_get_task(db, task.id))


@router.post("/{task_id}/claim", response_model=TaskOut)
def claim_task_owner(
    task_id: int,
    current: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> TaskOut:
    result = db.execute(
        update(Task)
        .where(
            Task.id == task_id,
            Task.owner_id.is_(None),
            Task.owner_claimable.is_(True),
            Task.status != "done",
        )
        .values(owner_id=current.id)
    )
    if result.rowcount != 1:
        db.rollback()
        if db.get(Task, task_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该任务当前不可认领")

    db.execute(
        delete(task_collaborators).where(
            task_collaborators.c.task_id == task_id,
            task_collaborators.c.member_id == current.id,
        )
    )
    db.commit()
    return _task_out(_get_task(db, task_id))


@router.post("/{task_id}/unclaim", response_model=TaskOut)
def unclaim_task_owner(
    task_id: int,
    current: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> TaskOut:
    task = _get_task(db, task_id)
    if task.owner_id != current.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有当前负责人可以取消认领")
    if task.status == "done":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="已完成任务不能取消认领")
    if not task.owner_claimable:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该任务不是公开认领任务")

    task.owner_id = None
    db.commit()
    db.expire(task)
    return _task_out(_get_task(db, task_id))


@router.post("/{task_id}/collaborators/join", response_model=TaskOut)
def join_task_collaboration(
    task_id: int,
    current: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> TaskOut:
    task = _get_task(db, task_id)
    if task.status == "done" or not task.collaboration_open:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该任务当前不开放协作")
    if task.owner_id == current.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="负责人无需重复加入协作")
    if all(member.id != current.id for member in task.collaborators):
        task.collaborators.append(current)
        db.commit()
        db.expire(task)
    return _task_out(_get_task(db, task_id))


@router.post("/{task_id}/collaborators/leave", response_model=TaskOut)
def leave_task_collaboration(
    task_id: int,
    current: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> TaskOut:
    task = _get_task(db, task_id)
    if task.status == "done":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="已完成任务不能退出协作")
    if not task.collaboration_open:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该任务未开放自主协作")

    task.collaborators = [member for member in task.collaborators if member.id != current.id]
    db.commit()
    db.expire(task)
    return _task_out(_get_task(db, task_id))
