"""API routes: JSON for scenarios, attempts, stats."""
import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.models.progress import Progress
from app.models.scenario import Scenario
from app.models.attempt import Attempt
from app.schemas.scenario import ScenarioOutSchema, ScenarioSubmitSchema, ChoiceSchema
from app.schemas.stats import StatsOutSchema, TacticBreakdownSchema
from app.services.scoring import (
    INITIAL_RISK_SCORE,
    apply_score_delta,
    compute_level,
    compute_achievements,
    get_tips_for_weak_tactics,
)

router = APIRouter(prefix="/api", tags=["api"])
settings = get_settings()


def get_or_create_session_id(request: Request) -> str:
    sid = request.cookies.get(settings.session_cookie_name)
    if not sid:
        sid = str(uuid.uuid4())
    return sid


async def get_or_create_progress(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Progress:
    sid = get_or_create_session_id(request)

    result = await db.execute(select(Progress).where(Progress.session_id == sid))
    progress = result.scalar_one_or_none()

    if progress is None:
        progress = Progress(
            session_id=sid,
            risk_score=INITIAL_RISK_SCORE,
            total_attempted=0,
            correct_count=0,
            current_streak=0,
        )
        db.add(progress)
        await db.commit()
        await db.refresh(progress)

    return progress


@router.get("/scenarios/{scenario_id}", response_model=ScenarioOutSchema)
async def get_scenario(
    scenario_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get one scenario by ID."""
    result = await db.execute(select(Scenario).where(Scenario.id == scenario_id))
    scenario = result.scalar_one_or_none()

    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    choices = [ChoiceSchema(**c) for c in json.loads(scenario.choices_json)]
    return ScenarioOutSchema(
        id=scenario.id,
        title=scenario.title,
        channel=scenario.channel,
        message_text=scenario.message_text,
        tactic=scenario.tactic,
        choices=choices,
    )


@router.post("/attempts")
async def submit_attempt(
    request: Request,
    body: ScenarioSubmitSchema,
    db: Annotated[AsyncSession, Depends(get_db)],
    progress: Annotated[Progress, Depends(get_or_create_progress)],
):
    """Submit a choice; return updated stats."""
    result = await db.execute(select(Scenario).where(Scenario.id == body.scenario_id))
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    choices_data = json.loads(scenario.choices_json)
    if body.choice_index < 0 or body.choice_index >= len(choices_data):
        raise HTTPException(status_code=400, detail="Invalid choice")

    choice = choices_data[body.choice_index]
    is_safe = bool(choice["is_safe"])
    score_delta = int(choice["score_delta"])

    progress.risk_score = apply_score_delta(progress.risk_score, score_delta)
    progress.total_attempted += 1
    if is_safe:
        progress.correct_count += 1
        progress.current_streak = (getattr(progress, "current_streak", 0) or 0) + 1
    else:
        progress.current_streak = 0

    db.add(
        Attempt(
            progress_id=progress.id,
            scenario_id=scenario.id,
            choice_index=body.choice_index,
            is_safe=is_safe,
            tactic=scenario.tactic,
        )
    )

    await db.commit()
    await db.refresh(progress)

    level = compute_level(progress.risk_score)
    return {
        "risk_score": progress.risk_score,
        "level": level,
        "total_attempted": progress.total_attempted,
        "correct_count": progress.correct_count,
        "current_streak": getattr(progress, "current_streak", 0),
        "is_safe": is_safe,
        "explanation": choice["explanation"],
        "tactic": scenario.tactic,
    }


@router.get("/stats", response_model=StatsOutSchema)
async def get_stats(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    progress: Annotated[Progress, Depends(get_or_create_progress)],
):
    """Get current stats: risk_score, level, tactic breakdown, tips, current_streak, safe_percentage, achievements."""
    # mistakes by tactic (unsafe attempts)
    result = await db.execute(
        select(Attempt.tactic, func.count(Attempt.id).label("cnt"))
        .where(
            Attempt.progress_id == progress.id,
            Attempt.is_safe == False,  # noqa: E712
        )
        .group_by(Attempt.tactic)
    )
    rows = result.all()

    tactic_breakdown = [TacticBreakdownSchema(tactic=t, mistake_count=c) for (t, c) in rows]
    all_tactics = ["Urgency", "Authority", "Scarcity", "Reciprocity", "Fear"]
    by_tactic = {t.tactic: t.mistake_count for t in tactic_breakdown}
    tactic_breakdown = [
        TacticBreakdownSchema(tactic=t, mistake_count=by_tactic.get(t, 0)) for t in all_tactics
    ]

    tips = get_tips_for_weak_tactics(tactic_breakdown, max_tips=3)
    level = compute_level(progress.risk_score)
    safe_pct = (progress.correct_count / progress.total_attempted * 100) if progress.total_attempted else 0.0

    # IMPORTANT: with AsyncSession don't rely on lazy relationship loading
    attempts_result = await db.execute(
        select(Attempt).where(Attempt.progress_id == progress.id).order_by(Attempt.id.asc())
    )
    attempts = attempts_result.scalars().all()

    achievements = compute_achievements(progress, list(attempts))

    return StatsOutSchema(
        risk_score=progress.risk_score,
        level=level,
        total_attempted=progress.total_attempted,
        correct_count=progress.correct_count,
        tactic_breakdown=tactic_breakdown,
        tips=tips,
        current_streak=getattr(progress, "current_streak", 0),
        safe_percentage=round(safe_pct, 1),
        achievements=achievements,
    )
