from __future__ import annotations

import io
import os
import re
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import SchoolLeaveRequest, SchoolLeaveRun


DEFAULT_SCHOOL_LEAVE_REASON = "参加吉林大学吉甲大师机器人战队相关创新实践活动及工作安排"
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
_CUTOFF_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


@dataclass(frozen=True)
class SchoolLeaveGroup:
    index: int
    start_at: datetime
    end_at: datetime
    requests: tuple[SchoolLeaveRequest, ...]


def school_leave_now() -> datetime:
    return datetime.now(SHANGHAI_TZ).replace(tzinfo=None, second=0, microsecond=0)


def get_leave_contact_phone() -> str:
    return os.getenv("LEAVE_CONTACT_PHONE", "").strip()


def get_leave_daily_cutoff() -> str:
    value = os.getenv("LEAVE_DAILY_CUTOFF", "").strip()
    if not _CUTOFF_RE.fullmatch(value):
        raise ValueError("LEAVE_DAILY_CUTOFF 必须配置为 HH:MM 24 小时格式")
    return value


def collect_pending_school_leave(
    db: Session,
    *,
    created_by: int | None,
    collected_at: datetime | None = None,
) -> SchoolLeaveRun | None:
    """Freeze every request that is pending at the collection transaction boundary."""
    try:
        pending = list(
            db.scalars(
                select(SchoolLeaveRequest)
                .where(SchoolLeaveRequest.status == "pending")
                .order_by(SchoolLeaveRequest.id)
                .with_for_update()
            )
        )
        if not pending:
            db.commit()
            return None

        run = SchoolLeaveRun(
            collected_at=collected_at or school_leave_now(),
            created_by=created_by,
            reason=DEFAULT_SCHOOL_LEAVE_REASON,
            status="ready",
        )
        db.add(run)
        db.flush()
        for request in pending:
            request.status = "included"
            request.run_id = run.id
        db.commit()
        db.refresh(run)
        return run
    except Exception:
        db.rollback()
        raise


def requests_for_run(db: Session, run_id: int) -> list[SchoolLeaveRequest]:
    return list(
        db.scalars(
            select(SchoolLeaveRequest)
            .where(
                SchoolLeaveRequest.run_id == run_id,
                SchoolLeaveRequest.status == "included",
            )
            .order_by(
                SchoolLeaveRequest.start_at,
                SchoolLeaveRequest.end_at,
                SchoolLeaveRequest.student_id_snapshot,
                SchoolLeaveRequest.member_name_snapshot,
                SchoolLeaveRequest.id,
            )
        )
    )


def group_school_leave_requests(requests: list[SchoolLeaveRequest]) -> list[SchoolLeaveGroup]:
    grouped: dict[tuple[datetime, datetime], list[SchoolLeaveRequest]] = {}
    for request in sorted(
        requests,
        key=lambda item: (
            item.start_at,
            item.end_at,
            item.student_id_snapshot,
            item.member_name_snapshot,
            item.id,
        ),
    ):
        grouped.setdefault((request.start_at, request.end_at), []).append(request)

    return [
        SchoolLeaveGroup(
            index=index,
            start_at=start_at,
            end_at=end_at,
            requests=tuple(items),
        )
        for index, ((start_at, end_at), items) in enumerate(grouped.items())
    ]


def format_school_leave_time(start_at: datetime, end_at: datetime) -> str:
    if start_at.date() == end_at.date():
        return (
            f"{start_at.year} 年 {start_at.month} 月 {start_at.day} 日 "
            f"{start_at:%H:%M} 至 {end_at:%H:%M}"
        )
    return (
        f"{start_at.year} 年 {start_at.month} 月 {start_at.day} 日 {start_at:%H:%M} 至\n"
        f"{end_at.year} 年 {end_at.month} 月 {end_at.day} 日 {end_at:%H:%M}"
    )


def _set_run_font(run, font_name: str, size: int, *, bold: bool | None = None) -> None:
    run.font.name = font_name
    run.font.size = Pt(size)
    run._element.rPr.rFonts.set(qn("w:eastAsia"), font_name)
    if bold is not None:
        run.bold = bold


def _set_cell_text(cell, text: str, *, bold: bool = False) -> None:
    paragraph = cell.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run(text)
    _set_run_font(run, "宋体", 12, bold=bold)


def _configure_school_leave_document(document: Document) -> None:
    normal_style = document.styles["Normal"]
    normal_style.font.name = "宋体"
    normal_style.font.size = Pt(14)
    normal_style._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")


def _append_school_leave_group(
    document: Document,
    run: SchoolLeaveRun,
    group: SchoolLeaveGroup,
    *,
    contact_phone: str,
) -> None:
    title = document.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title.add_run("请假条")
    _set_run_font(title_run, "黑体", 18, bold=True)

    time_text = format_school_leave_time(group.start_at, group.end_at)
    body = document.add_paragraph()
    body.paragraph_format.first_line_indent = Pt(28)
    body.paragraph_format.line_spacing = 1.5
    body_run = body.add_run(
        f"以下学生因{run.reason}，需于{time_text}期间请假，"
        "无法正常参加对应时段课程，特此证明。"
    )
    _set_run_font(body_run, "宋体", 14)

    signature = document.add_paragraph()
    signature_run = signature.add_run("指导教师（签字）：")
    _set_run_font(signature_run, "宋体", 14)

    phone = document.add_paragraph()
    phone_run = phone.add_run(f"联系电话：{contact_phone.strip()}")
    _set_run_font(phone_run, "宋体", 14)

    issued = document.add_paragraph()
    issued.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    issued_run = issued.add_run(
        f"{run.collected_at.year} 年 {run.collected_at.month} 月 {run.collected_at.day} 日"
    )
    _set_run_font(issued_run, "宋体", 14)

    table = document.add_table(rows=1, cols=2)
    table.style = "Table Grid"
    _set_cell_text(table.rows[0].cells[0], "姓名", bold=True)
    _set_cell_text(table.rows[0].cells[1], "学号", bold=True)
    for request in group.requests:
        cells = table.add_row().cells
        _set_cell_text(cells[0], request.member_name_snapshot)
        _set_cell_text(cells[1], request.student_id_snapshot)


def build_school_leave_docx(
    run: SchoolLeaveRun,
    group: SchoolLeaveGroup,
    *,
    contact_phone: str,
) -> bytes:
    """Build one exact-time group DOCX for backward-compatible downloads."""
    if not contact_phone.strip():
        raise ValueError("LEAVE_CONTACT_PHONE 未配置，无法生成学校请假材料")

    document = Document()
    _configure_school_leave_document(document)
    _append_school_leave_group(document, run, group, contact_phone=contact_phone)

    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


def build_school_leave_run_docx(
    run: SchoolLeaveRun,
    groups: list[SchoolLeaveGroup],
    *,
    contact_phone: str,
) -> bytes:
    """Build one DOCX for a run, with each exact-time group on its own page."""
    if not contact_phone.strip():
        raise ValueError("LEAVE_CONTACT_PHONE 未配置，无法生成学校请假材料")
    if not groups:
        raise ValueError("该汇总批次没有可生成的请假材料")

    document = Document()
    _configure_school_leave_document(document)
    for index, group in enumerate(groups):
        _append_school_leave_group(document, run, group, contact_phone=contact_phone)
        if index < len(groups) - 1:
            document.add_page_break()

    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


def school_leave_document_filename(group: SchoolLeaveGroup) -> str:
    start = group.start_at.strftime("%Y-%m-%d_%H%M")
    end = group.end_at.strftime("%Y-%m-%d_%H%M")
    return f"请假条_{start}-{end}.docx"


def school_leave_run_document_filename(run: SchoolLeaveRun) -> str:
    date_text = run.collected_at.strftime("%Y-%m-%d")
    return f"学校请假材料_{date_text}_批次{run.id}.docx"
