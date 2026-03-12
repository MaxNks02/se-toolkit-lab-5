import httpx
from datetime import datetime
from sqlalchemy import select, func
from sqlmodel.ext.asyncio.session import AsyncSession

from app.settings import settings
from app.models.item import ItemRecord
from app.models.learner import Learner
from app.models.interaction import InteractionLog


# ---------------------------------------------------------------------------
# Extract — fetch data from the autochecker API
# ---------------------------------------------------------------------------

async def fetch_items() -> list[dict]:
    """Fetch the lab/task catalog from the autochecker API."""
    auth = (settings.autochecker_email, settings.autochecker_password)
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{settings.autochecker_api_url}/api/items", auth=auth)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch items: {response.status_code}")
        return response.json()


async def fetch_logs(since: datetime | None = None) -> list[dict]:
    """Fetch check results from the autochecker API with pagination."""
    auth = (settings.autochecker_email, settings.autochecker_password)
    all_logs = []
    has_more = True
    current_since = since.isoformat() if since else None

    async with httpx.AsyncClient() as client:
        while has_more:
            params = {"limit": 500}
            if current_since:
                params["since"] = current_since

            response = await client.get(f"{settings.autochecker_api_url}/api/logs", auth=auth, params=params)
            data = response.json()

            logs = data.get("logs", [])
            all_logs.extend(logs)
            has_more = data.get("has_more", False)

            if has_more and logs:
                current_since = logs[-1]["submitted_at"]

    return all_logs


# ---------------------------------------------------------------------------
# Load — insert fetched data into the local database
# ---------------------------------------------------------------------------

async def load_items(items: list[dict], session: AsyncSession) -> int:
    """Load items (labs and tasks) into the database."""
    new_count = 0
    lab_map = {}  # Maps lab short ID (e.g. "lab-01") to DB record

    # Process labs first
    for item in [i for i in items if i["type"] == "lab"]:
        statement = select(ItemRecord).where(ItemRecord.type == "lab", ItemRecord.title == item["title"])
        # FIXED: Added .scalars() to return the object, not a tuple
        existing = (await session.exec(statement)).scalars().first()

        if not existing:
            existing = ItemRecord(type="lab", title=item["title"])
            session.add(existing)
            new_count += 1
            await session.flush()  # Get ID for the lab record

        lab_map[item["lab"]] = existing

    # Process tasks
    for item in [i for i in items if i["type"] == "task"]:
        parent_lab = lab_map.get(item["lab"])
        if not parent_lab:
            continue

        statement = select(ItemRecord).where(
            ItemRecord.title == item["title"],
            ItemRecord.parent_id == parent_lab.id
        )
        # FIXED: Added .scalars() to ensure .id access works
        existing = (await session.exec(statement)).scalars().first()

        if not existing:
            session.add(ItemRecord(type="task", title=item["title"], parent_id=parent_lab.id))
            new_count += 1

    await session.commit()
    return new_count


async def load_logs(logs: list[dict], items_catalog: list[dict], session: AsyncSession) -> int:
    """Load interaction logs into the database with idempotency."""
    new_interactions = 0

    # FIXED: Use .scalars().all() to get actual ItemRecord objects
    item_statement = select(ItemRecord)
    db_items = (await session.exec(item_statement)).scalars().all()

    catalog_map = {(i["lab"], i["task"]): i["title"] for i in items_catalog}
    db_lookup = {}

    # Map lab slug (from API) to lab ID (from DB)
    lab_slug_to_id = {
        i["lab"]: db_item.id for i in items_catalog for db_item in db_items
        if i["type"] == "lab" and i["title"] == db_item.title
    }

    for db_item in db_items:
        if db_item.type == "task":
            for (l_slug, t_slug), title in catalog_map.items():
                if title == db_item.title and db_item.parent_id == lab_slug_to_id.get(l_slug):
                    db_lookup[(l_slug, t_slug)] = db_item.id

    for log in logs:
        # Find or create Learner
        statement = select(Learner).where(Learner.external_id == log["student_id"])
        # FIXED: Added .scalars()
        learner = (await session.exec(statement)).scalars().first()
        if not learner:
            learner = Learner(external_id=log["student_id"], student_group=log["group"])
            session.add(learner)
            await session.flush()

        # Find Item ID
        item_id = db_lookup.get((log["lab"], log["task"]))
        if not item_id:
            continue

        # Idempotent check
        # FIXED: Added .scalars() to ensure it doesn't return a tuple
        existing_log = (await session.exec(
            select(InteractionLog).where(InteractionLog.external_id == log["id"])
        )).scalars().first()
        if existing_log:
            continue

        session.add(InteractionLog(
            external_id=log["id"],
            learner_id=learner.id,
            item_id=item_id,
            kind="attempt",
            score=log["score"],
            checks_passed=log["passed"],
            checks_total=log["total"],
            created_at=datetime.fromisoformat(log["submitted_at"].replace("Z", "+00:00"))
        ))
        new_interactions += 1

    await session.commit()
    return new_interactions


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

async def sync(session: AsyncSession) -> dict:
    """Run the full ETL pipeline."""
    raw_items = await fetch_items()
    await load_items(raw_items, session)

    last_interaction_stmt = select(InteractionLog).order_by(InteractionLog.created_at.desc())
    last_interaction = (await session.exec(last_interaction_stmt)).scalars().first()
    since = last_interaction.created_at if last_interaction else None

    raw_logs = await fetch_logs(since=since)
    new_count = await load_logs(raw_logs, raw_items, session)

    # CHANGE THIS LINE:
    # Use .scalar() instead of .one() to get the raw integer value
    total_count = await session.scalar(select(func.count(InteractionLog.id)))

    return {"new_records": new_count, "total_records": total_count}