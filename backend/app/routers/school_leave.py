from __future__ import annotations

import io
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..auth import get_current_member, require_admin
from ..db import get_db
from ..models import Member, SchoolLeaveRequest, SchoolLeaveRun
from ..schemas import (
    MemberSummary,
    SchoolLeaveAdminConfigOut,
    SchoolLeaveGroupMemberOut,
    SchoolLeaveGroupOut,
    SchoolLeaveReasonUpdate,
    SchoolLeaveRequestCreate,
    SchoolLeaveRequestOut,
    SchoolLeaveRequestUpdate,
    SchoolLeaveRunOut,
)
from ..school_leave import (
    build_school_leave_docx,
    build_school_leave_run_docx,
    collect_pending_school_leave,
    format_school_leave_time,
    get_leave_contact_phone,
    get_leave_daily_cutoff,
    group_school_leave_requests,
    requests_for_run,
    school_leave_document_filename,
    school_leave_run_document_filename,
    school_leave_now,
)


router = APIRouter(prefix="/api/school-leave", tags=["school-leave"])


def _request_out(request: SchoolLeaveRequest) -> SchoolLeaveRequestOut:
    return SchoolLeaveRequestOut.model_validate(request)


def _run_out(db: Session, run: SchoolLeaveRun) -> SchoolLeaveRunOut:
    requests = requests_for_run(db, run.id)
    groups = group_school_leave_requests(requests)
    creator = db.get(Member, run.created_by) if run.created_by is not None else None
    sender = db.get(Member, run.sent_by) if run.sent_by is not None else None
    group_outputs = [
        SchoolLeaveGroupOut(
            index=group.index,
            start_at=group.start_at,
            end_at=group.end_at,
            time_text=format_school_leave_time(group.start_at, group.end_at),
            count=len(group.requests),
            members=[
                SchoolLeaveGroupMemberOut(
                    member_id=request.member_id,
                    name=request.member_name_snapshot,
                    student_id=request.student_id_snapshot,
                )
                for request in group.requests
            ],
        )
        for group in groups
    ]
    return SchoolLeaveRunOut(
        id=run.id,
        collected_at=run.collected_at,
        created_by=MemberSummary.model_validate(creator) if creator else None,
        reason=run.reason,
        status=run.status,
        sent_at=run.sent_at,
        sent_by=MemberSummary.model_validate(sender) if sender else None,
        request_count=len(requests),
        member_count=len({request.member_id for request in requests}),
        groups=group_outputs,
        document_ready=bool(get_leave_contact_phone()),
    )


def _get_owned_request(
    db: Session,
    request_id: int,
    member_id: int,
    *,
    lock: bool = False,
) -> SchoolLeaveRequest:
    query = select(SchoolLeaveRequest).where(
        SchoolLeaveRequest.id == request_id,
        SchoolLeaveRequest.member_id == member_id,
    )
    if lock:
        query = query.with_for_update()
    request = db.scalar(query)
    if not request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="请假申请不存在")
    return request


def _get_admin_run(db: Session, run_id: int, *, lock: bool = False) -> SchoolLeaveRun:
    query = select(SchoolLeaveRun).where(SchoolLeaveRun.id == run_id)
    if lock:
        query = query.with_for_update()
    run = db.scalar(query)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="汇总批次不存在")
    return run


@router.get("/requests", response_model=list[SchoolLeaveRequestOut])
def list_my_requests(
    current: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> list[SchoolLeaveRequestOut]:
    requests = list(
        db.scalars(
            select(SchoolLeaveRequest)
            .where(SchoolLeaveRequest.member_id == current.id)
            .order_by(SchoolLeaveRequest.created_at.desc(), SchoolLeaveRequest.id.desc())
        )
    )
    return [_request_out(request) for request in requests]


@router.post("/requests", response_model=SchoolLeaveRequestOut, status_code=status.HTTP_201_CREATED)
def create_request(
    payload: SchoolLeaveRequestCreate,
    current: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> SchoolLeaveRequestOut:
    if not current.student_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="请先完善学号，生成学校请假材料时需要使用。",
        )
    request = SchoolLeaveRequest(
        member_id=current.id,
        start_at=payload.start_at,
        end_at=payload.end_at,
        member_name_snapshot=current.name,
        student_id_snapshot=current.student_id,
        status="pending",
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return _request_out(request)


@router.patch("/requests/{request_id}", response_model=SchoolLeaveRequestOut)
def update_request(
    request_id: int,
    payload: SchoolLeaveRequestUpdate,
    current: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> SchoolLeaveRequestOut:
    request = _get_owned_request(db, request_id, current.id, lock=True)
    if request.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该申请已汇总，不能直接修改")
    request.start_at = payload.start_at
    request.end_at = payload.end_at
    db.commit()
    db.refresh(request)
    return _request_out(request)


@router.post("/requests/{request_id}/withdraw", response_model=SchoolLeaveRequestOut)
def withdraw_request(
    request_id: int,
    current: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> SchoolLeaveRequestOut:
    request = _get_owned_request(db, request_id, current.id, lock=True)
    if request.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="只有待汇总申请可以撤回")
    request.status = "withdrawn"
    db.commit()
    db.refresh(request)
    return _request_out(request)


@router.get("/admin/config", response_model=SchoolLeaveAdminConfigOut)
def admin_config(
    _: Member = Depends(require_admin),
) -> SchoolLeaveAdminConfigOut:
    try:
        cutoff = get_leave_daily_cutoff()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return SchoolLeaveAdminConfigOut(
        daily_cutoff=cutoff,
        contact_phone_configured=bool(get_leave_contact_phone()),
    )


@router.get("/admin/requests", response_model=list[SchoolLeaveRequestOut])
def admin_list_requests(
    _: Member = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[SchoolLeaveRequestOut]:
    requests = list(
        db.scalars(
            select(SchoolLeaveRequest).order_by(
                SchoolLeaveRequest.created_at.desc(),
                SchoolLeaveRequest.id.desc(),
            )
        )
    )
    return [_request_out(request) for request in requests]


@router.get("/admin/runs", response_model=list[SchoolLeaveRunOut])
def admin_list_runs(
    _: Member = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[SchoolLeaveRunOut]:
    runs = list(
        db.scalars(
            select(SchoolLeaveRun).order_by(
                SchoolLeaveRun.collected_at.desc(),
                SchoolLeaveRun.id.desc(),
            )
        )
    )
    return [_run_out(db, run) for run in runs]


@router.post("/admin/runs/collect", response_model=SchoolLeaveRunOut | None)
def admin_collect(
    current: Member = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SchoolLeaveRunOut | None:
    run = collect_pending_school_leave(db, created_by=current.id)
    return _run_out(db, run) if run else None


@router.patch("/admin/runs/{run_id}/reason", response_model=SchoolLeaveRunOut)
def update_run_reason(
    run_id: int,
    payload: SchoolLeaveReasonUpdate,
    _: Member = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SchoolLeaveRunOut:
    run = _get_admin_run(db, run_id, lock=True)
    if run.status != "ready":
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="只有待发送批次可以修改事由")
    run.reason = payload.reason
    db.commit()
    db.refresh(run)
    return _run_out(db, run)


@router.post("/admin/runs/{run_id}/cancel", response_model=SchoolLeaveRunOut)
def cancel_run(
    run_id: int,
    _: Member = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SchoolLeaveRunOut:
    try:
        run = _get_admin_run(db, run_id, lock=True)
        if run.status != "ready":
            db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="只有待发送批次可以取消")
        requests = list(
            db.scalars(
                select(SchoolLeaveRequest)
                .where(
                    SchoolLeaveRequest.run_id == run.id,
                    SchoolLeaveRequest.status == "included",
                )
                .order_by(SchoolLeaveRequest.id)
                .with_for_update()
            )
        )
        for request in requests:
            request.status = "pending"
            request.run_id = None
        run.status = "cancelled"
        db.commit()
        db.refresh(run)
        return _run_out(db, run)
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise


@router.post("/admin/runs/{run_id}/sent", response_model=SchoolLeaveRunOut)
def mark_run_sent(
    run_id: int,
    current: Member = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SchoolLeaveRunOut:
    run = _get_admin_run(db, run_id, lock=True)
    if run.status != "ready":
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="只有待发送批次可以标记已发送")
    run.status = "sent"
    run.sent_at = school_leave_now()
    run.sent_by = current.id
    db.commit()
    db.refresh(run)
    return _run_out(db, run)


@router.delete("/admin/runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_run_history(
    run_id: int,
    _: Member = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    try:
        run = _get_admin_run(db, run_id, lock=True)
        if run.status == "ready":
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="待发送批次不能直接删除，请先取消本次汇总",
            )
        linked_requests = list(
            db.scalars(
                select(SchoolLeaveRequest)
                .where(SchoolLeaveRequest.run_id == run.id)
                .order_by(SchoolLeaveRequest.id)
                .with_for_update()
            )
        )
        if linked_requests:
            request_ids = [request.id for request in linked_requests]
            db.execute(delete(SchoolLeaveRequest).where(SchoolLeaveRequest.id.in_(request_ids)))
        db.delete(run)
        db.commit()
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise


def _document_context(
    db: Session,
    run_id: int,
) -> tuple[SchoolLeaveRun, list]:
    run = _get_admin_run(db, run_id)
    if run.status == "cancelled":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="已取消批次不能生成材料")
    contact_phone = get_leave_contact_phone()
    if not contact_phone:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LEAVE_CONTACT_PHONE 未配置，暂时不能生成学校请假材料",
        )
    groups = group_school_leave_requests(requests_for_run(db, run.id))
    if not groups:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该批次没有可生成的请假材料")
    return run, groups


@router.get("/admin/runs/{run_id}/documents/{group_index}")
def download_document(
    run_id: int,
    group_index: int,
    _: Member = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    run, groups = _document_context(db, run_id)
    group = next((item for item in groups if item.index == group_index), None)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="时间组不存在")
    content = build_school_leave_docx(run, group, contact_phone=get_leave_contact_phone())
    filename = school_leave_document_filename(group)
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/admin/runs/{run_id}/document")
def download_run_document(
    run_id: int,
    _: Member = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    run, groups = _document_context(db, run_id)
    content = build_school_leave_run_docx(
        run,
        groups,
        contact_phone=get_leave_contact_phone(),
    )
    filename = school_leave_run_document_filename(run)
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )
