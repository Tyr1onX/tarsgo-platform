from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session, selectinload

from ..auth import get_current_member, require_manager
from ..db import get_db
from ..models import ItemActivity, Member, Task, task_collaborators
from ..schemas import (
    ItemActivityCreate,
    ItemActivityOut,
    ItemFactCreate,
    MemberSummary,
    TaskBatchCreate,
    TaskBatchOut,
    TaskCreate,
    TaskOut,
    TaskUpdate,
)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _is_manager(member: Member) -> bool:
    return member.role in {"admin", "manager"}


def _task_query():
    return select(Task).options(selectinload(Task.owner), selectinload(Task.collaborators))


def _activity_query():
    return select(ItemActivity).options(selectinload(ItemActivity.author))


def _task_out(task: Task) -> TaskOut:
    return TaskOut(
        id=task.id,
        parent_id=task.parent_id,
        title=task.title,
        deliverable=task.deliverable,
        execution_points=task.execution_points or [],
        cautions=task.cautions or [],
        prerequisites=task.prerequisites or [],
        context_facts=task.context_facts or [],
        result=task.result or "",
        owner=MemberSummary.model_validate(task.owner) if task.owner else None,
        owner_claimable=task.owner_claimable,
        collaborators=[MemberSummary.model_validate(member) for member in task.collaborators],
        collaboration_open=task.collaboration_open,
        deadline=task.deadline,
        status=task.status,
        created_by=task.created_by,
        created_at=task.created_at,
    )


def _activity_out(activity: ItemActivity) -> ItemActivityOut:
    return ItemActivityOut(
        id=activity.id,
        root_task_id=activity.root_task_id,
        author=MemberSummary.model_validate(activity.author),
        content=activity.content,
        created_at=activity.created_at,
    )


def _load_active_members(db: Session, member_ids: set[int]) -> dict[int, Member]:
    if not member_ids:
        return {}
    members = {
        member.id: member
        for member in db.scalars(select(Member).where(Member.id.in_(member_ids), Member.status == "active"))
    }
    if members.keys() != member_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="负责人或协作者不存在或未激活")
    return members


def _get_task(db: Session, task_id: int) -> Task:
    task = db.scalar(_task_query().where(Task.id == task_id))
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return task


def _get_root_task(db: Session, task_id: int) -> Task:
    task = _get_task(db, task_id)
    if task.parent_id is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="事项动态只能挂在事项上")
    return task


def _root_for_task(db: Session, task: Task) -> Task:
    return task if task.parent_id is None else _get_root_task(db, task.parent_id)


def _can_write_item(db: Session, root: Task, current: Member) -> bool:
    if _is_manager(current) or root.owner_id == current.id:
        return True
    child_id = db.scalar(
        select(Task.id)
        .where(
            Task.parent_id == root.id,
            or_(
                Task.owner_id == current.id,
                Task.collaborators.any(Member.id == current.id),
            ),
        )
        .limit(1)
    )
    return child_id is not None


def _require_item_writer(db: Session, root: Task, current: Member) -> None:
    if not _can_write_item(db, root, current):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有事项参与者可以更新事项信息")


def _append_context_fact(root: Task, content: str) -> None:
    facts = list(root.context_facts or [])
    if len(content) > 500:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="当前信息单条最多 500 字")
    if len(facts) >= 30:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="当前信息最多保留 30 条")
    root.context_facts = [*facts, content]


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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="任务必须指定负责人或开放负责人认领")


def _build_task(db: Session, payload: TaskCreate, current: Member) -> Task:
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
        execution_points=payload.execution_points,
        cautions=payload.cautions,
        prerequisites=payload.prerequisites,
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
    return task


@router.get("", response_model=list[TaskOut])
def list_tasks(
    scope: str = Query(default="mine", pattern="^(mine|claimable|all)$"),
    current: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> list[TaskOut]:
    query = _task_query()
    if scope == "mine":
        query = query.where(or_(Task.owner_id == current.id, Task.collaborators.any(Member.id == current.id)))
    elif scope == "claimable":
        query = query.where(Task.owner_id.is_(None), Task.owner_claimable.is_(True), Task.status != "done")

    tasks = db.scalars(query.order_by(Task.deadline.asc(), Task.id.asc())).unique().all()
    return [_task_out(task) for task in tasks]


@router.get("/assignees", response_model=list[MemberSummary])
def list_task_assignees(_: Member = Depends(require_manager), db: Session = Depends(get_db)) -> list[Member]:
    return list(db.scalars(select(Member).where(Member.status == "active").order_by(Member.name.asc(), Member.id.asc())))


@router.get("/{task_id}", response_model=TaskOut)
def get_task(
    task_id: int,
    _: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> TaskOut:
    return _task_out(_get_task(db, task_id))


@router.get("/{root_task_id}/activities", response_model=list[ItemActivityOut])
def list_item_activities(
    root_task_id: int,
    _: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> list[ItemActivityOut]:
    root = _get_root_task(db, root_task_id)
    activities = db.scalars(
        _activity_query()
        .where(ItemActivity.root_task_id == root.id)
        .order_by(ItemActivity.created_at.desc(), ItemActivity.id.desc())
    ).all()
    return [_activity_out(activity) for activity in activities]


@router.post("/{root_task_id}/activities", response_model=ItemActivityOut, status_code=status.HTTP_201_CREATED)
def create_item_activity(
    root_task_id: int,
    payload: ItemActivityCreate,
    current: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> ItemActivityOut:
    root = _get_root_task(db, root_task_id)
    _require_item_writer(db, root, current)
    activity = ItemActivity(root_task_id=root.id, author_id=current.id, content=payload.content)
    try:
        db.add(activity)
        if payload.add_to_context:
            _append_context_fact(root, payload.content)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    db.expire(activity)
    saved = db.scalar(_activity_query().where(ItemActivity.id == activity.id))
    if saved is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="动态保存失败")
    return _activity_out(saved)


@router.post("/{root_task_id}/context-facts", response_model=TaskOut)
def add_context_fact(
    root_task_id: int,
    payload: ItemFactCreate,
    current: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> TaskOut:
    root = _get_root_task(db, root_task_id)
    _require_item_writer(db, root, current)
    _append_context_fact(root, payload.content)
    db.commit()
    return _task_out(_get_task(db, root.id))


@router.delete("/{root_task_id}/context-facts/{fact_index}", response_model=TaskOut)
def delete_context_fact(
    root_task_id: int,
    fact_index: int,
    current: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> TaskOut:
    root = _get_root_task(db, root_task_id)
    _require_item_writer(db, root, current)
    facts = list(root.context_facts or [])
    if fact_index < 0 or fact_index >= len(facts):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="当前信息不存在")
    root.context_facts = [fact for index, fact in enumerate(facts) if index != fact_index]
    db.commit()
    return _task_out(_get_task(db, root.id))


@router.post("/{task_id}/result-to-context", response_model=TaskOut)
def add_task_result_to_context(
    task_id: int,
    current: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> TaskOut:
    task = _get_task(db, task_id)
    root = _root_for_task(db, task)
    _require_item_writer(db, root, current)
    result = (task.result or "").strip()
    if not result:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="请先填写执行结果")
    activity = ItemActivity(
        root_task_id=root.id,
        author_id=current.id,
        content=f"任务「{task.title}」的执行结果已确认加入事项信息。",
    )
    try:
        _append_context_fact(root, result)
        db.add(activity)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    return _task_out(_get_task(db, root.id))


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, current: Member = Depends(require_manager), db: Session = Depends(get_db)) -> TaskOut:
    task = _build_task(db, payload, current)
    db.commit()
    db.expire(task)
    return _task_out(_get_task(db, task.id))


@router.post("/batch", response_model=TaskBatchOut, status_code=status.HTTP_201_CREATED)
def create_task_batch(
    payload: TaskBatchCreate,
    current: Member = Depends(require_manager),
    db: Session = Depends(get_db),
) -> TaskBatchOut:
    try:
        root = _build_task(
            db,
            TaskCreate(
                title=payload.item.title,
                deliverable=payload.item.deliverable,
                owner_id=current.id,
                owner_claimable=False,
                collaborator_ids=[],
                collaboration_open=False,
                parent_id=None,
                deadline=payload.item.deadline,
                status="todo",
            ),
            current,
        )
        db.flush()

        children: list[Task] = []
        for child in payload.tasks:
            children.append(
                _build_task(
                    db,
                    TaskCreate(
                        title=child.title,
                        deliverable=child.deliverable,
                        execution_points=child.execution_points,
                        cautions=child.cautions,
                        prerequisites=child.prerequisites,
                        owner_id=None if child.owner_claimable else current.id,
                        owner_claimable=child.owner_claimable,
                        collaborator_ids=[],
                        collaboration_open=child.collaboration_open,
                        parent_id=root.id,
                        deadline=payload.item.deadline,
                        status="todo",
                    ),
                    current,
                )
            )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return TaskBatchOut(
        item=_task_out(_get_task(db, root.id)),
        tasks=[_task_out(_get_task(db, child.id)) for child in children],
    )


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
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有负责人可以更新任务状态和执行结果")
        allowed_fields = {"status", "result"}
        if not fields or not fields.issubset(allowed_fields):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="普通成员只能更新自己负责任务的状态和执行结果")
        if "status" in fields:
            if payload.status is None:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="任务状态不能为空")
            task.status = payload.status
        if "result" in fields:
            if payload.result is None:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="执行结果不能为空")
            task.result = payload.result
        db.commit()
        db.expire(task)
        return _task_out(_get_task(db, task.id))

    required_non_null = {
        "title", "deliverable", "execution_points", "cautions", "prerequisites", "result",
        "collaborator_ids", "owner_claimable", "collaboration_open", "deadline", "status",
    }
    if any(field in fields and getattr(payload, field) is None for field in required_non_null):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="任务字段不能设为空")

    resulting_owner_id = payload.owner_id if "owner_id" in fields else task.owner_id
    resulting_claimable = payload.owner_claimable if "owner_claimable" in fields else task.owner_claimable
    _validate_owner_state(resulting_owner_id, bool(resulting_claimable))

    if "owner_id" in fields and resulting_owner_id is not None:
        _load_active_members(db, {resulting_owner_id})

    for field in (
        "title", "deliverable", "execution_points", "cautions", "prerequisites", "result",
        "owner_claimable", "collaboration_open", "deadline", "status",
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
        task.collaborators = [member for member in task.collaborators if member.id != resulting_owner_id]

    db.commit()
    db.expire(task)
    return _task_out(_get_task(db, task.id))


@router.post("/{task_id}/claim", response_model=TaskOut)
def claim_task_owner(task_id: int, current: Member = Depends(get_current_member), db: Session = Depends(get_db)) -> TaskOut:
    result = db.execute(
        update(Task)
        .where(Task.id == task_id, Task.owner_id.is_(None), Task.owner_claimable.is_(True), Task.status != "done")
        .values(owner_id=current.id)
    )
    if result.rowcount != 1:
        db.rollback()
        if db.get(Task, task_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该任务当前不可认领")

    db.execute(delete(task_collaborators).where(task_collaborators.c.task_id == task_id, task_collaborators.c.member_id == current.id))
    db.commit()
    return _task_out(_get_task(db, task_id))


@router.post("/{task_id}/unclaim", response_model=TaskOut)
def unclaim_task_owner(task_id: int, current: Member = Depends(get_current_member), db: Session = Depends(get_db)) -> TaskOut:
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
def join_task_collaboration(task_id: int, current: Member = Depends(get_current_member), db: Session = Depends(get_db)) -> TaskOut:
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
def leave_task_collaboration(task_id: int, current: Member = Depends(get_current_member), db: Session = Depends(get_db)) -> TaskOut:
    task = _get_task(db, task_id)
    if task.status == "done":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="已完成任务不能退出协作")
    if not task.collaboration_open:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该任务未开放自主协作")
    task.collaborators = [member for member in task.collaborators if member.id != current.id]
    db.commit()
    db.expire(task)
    return _task_out(_get_task(db, task_id))
