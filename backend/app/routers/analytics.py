from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, case, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models.item import ItemRecord
from app.models.interaction import InteractionLog
from app.models.learner import Learner

router = APIRouter()


async def get_lab_task_ids(lab_slug: str, session: AsyncSession) -> list[int]:
    """Helper to find all task IDs belonging to a specific lab slug."""
    # Convert 'lab-01' to 'Lab 01' for title matching
    lab_title_part = lab_slug.replace("-", " ").title()

    # Find the lab record
    lab_stmt = select(ItemRecord).where(
        ItemRecord.type == "lab",
        ItemRecord.title.ilike(f"%{lab_title_part}%")
    )
    # FIXED: Added .scalars().first() to get the actual object
    lab = (await session.exec(lab_stmt)).scalars().first()
    if not lab:
        return []

    # Find all tasks belonging to this lab
    task_stmt = select(ItemRecord.id).where(ItemRecord.parent_id == lab.id)
    # FIXED: Added .scalars().all() to return a list of integers
    return list((await session.exec(task_stmt)).scalars().all())


@router.get("/scores")
async def get_scores(
        lab: str = Query(..., description="Lab identifier, e.g. 'lab-01'"),
        session: AsyncSession = Depends(get_session),
):
    """Score distribution histogram for a given lab."""
    task_ids = await get_lab_task_ids(lab, session)
    if not task_ids:
        return []

    # Use CASE WHEN to bucket scores
    stmt = (
        select(
            case(
                (InteractionLog.score <= 25, "0-25"),
                (InteractionLog.score <= 50, "26-50"),
                (InteractionLog.score <= 75, "51-75"),
                else_="76-100"
            ).label("bucket"),
            func.count(InteractionLog.id).label("count")
        )
        .where(InteractionLog.item_id.in_(task_ids), InteractionLog.score.is_not(None))
        .group_by("bucket")
    )
    # result contains custom labels, so we access them via _mapping
    results = (await session.exec(stmt)).all()

    buckets = {"0-25": 0, "26-50": 0, "51-75": 0, "76-100": 0}
    for row in results:
        buckets[row.bucket] = row.count

    return [{"bucket": k, "count": v} for k, v in buckets.items()]


@router.get("/pass-rates")
async def get_pass_rates(
        lab: str = Query(..., description="Lab identifier, e.g. 'lab-01'"),
        session: AsyncSession = Depends(get_session),
):
    """Per-task pass rates for a given lab."""
    lab_title_part = lab.replace("-", " ").title()
    lab_stmt = select(ItemRecord).where(ItemRecord.type == "lab", ItemRecord.title.ilike(f"%{lab_title_part}%"))
    # FIXED: Added .scalars().first()
    lab_record = (await session.exec(lab_stmt)).scalars().first()

    if not lab_record:
        return []

    stmt = (
        select(
            ItemRecord.title.label("task"),
            func.round(func.avg(InteractionLog.score), 1).label("avg_score"),
            func.count(InteractionLog.id).label("attempts")
        )
        .join(InteractionLog, InteractionLog.item_id == ItemRecord.id)
        .where(ItemRecord.parent_id == lab_record.id)
        .group_by(ItemRecord.id)
        .order_by(ItemRecord.title)
    )
    # Aggregations return rows; use ._mapping to convert to dict safely
    results = (await session.exec(stmt)).all()
    return [dict(row._mapping) for row in results]


@router.get("/timeline")
async def get_timeline(
        lab: str = Query(..., description="Lab identifier, e.g. 'lab-01'"),
        session: AsyncSession = Depends(get_session),
):
    """Submissions per day for a given lab."""
    task_ids = await get_lab_task_ids(lab, session)
    if not task_ids:
        return []

    stmt = (
        select(
            func.date(InteractionLog.created_at).label("date"),
            func.count(InteractionLog.id).label("submissions")
        )
        .where(InteractionLog.item_id.in_(task_ids))
        .group_by(func.date(InteractionLog.created_at))
        .order_by("date")
    )
    results = (await session.exec(stmt)).all()
    return [{"date": str(row.date), "submissions": row.submissions} for row in results]


@router.get("/groups")
async def get_groups(
        lab: str = Query(..., description="Lab identifier, e.g. 'lab-01'"),
        session: AsyncSession = Depends(get_session),
):
    """Per-group performance for a given lab."""
    task_ids = await get_lab_task_ids(lab, session)
    if not task_ids:
        return []

    stmt = (
        select(
            Learner.student_group.label("group"),
            func.round(func.avg(InteractionLog.score), 1).label("avg_score"),
            func.count(func.distinct(Learner.id)).label("students")
        )
        .join(InteractionLog, InteractionLog.learner_id == Learner.id)
        .where(InteractionLog.item_id.in_(task_ids))
        .group_by(Learner.student_group)
        .order_by(Learner.student_group)
    )
    results = (await session.exec(stmt)).all()


    return [dict(row._mapping) for row in results]