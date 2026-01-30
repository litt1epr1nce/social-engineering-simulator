"""API routes: JSON for scenarios, attempts, stats."""
import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.progress import Progress
from app.models.scenario import Scenario
from app.models.attempt import Attempt
from app.schemas.scenario import ScenarioOutSchema, ScenarioSubmitSchema, ChoiceSchema
from app.schemas.stats import StatsOutSchema, TacticBreakdownSchema, AchievementSchema
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


def get_or_create_progress(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> Progress:
    sid = get_or_create_session_id(request)
    progress = db.query(Progress).filter(Progress.session_id == sid).first()
    if progress is None:
        progress = Progress(
            session_id=sid,
            risk_score=INITIAL_RISK_SCORE,
            total_attempted=0,
            correct_count=0,
            current_streak=0,
        )
        db.add(progress)
        db.commit()
        db.refresh(progress)
    return progress


@router.get("/scenarios/{scenario_id}", response_model=ScenarioOutSchema)
def get_scenario(scenario_id: int, db: Annotated[Session, Depends(get_db)]):
    """Get one scenario by ID."""
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
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
def submit_attempt(
    request: Request,
    body: ScenarioSubmitSchema,
    db: Annotated[Session, Depends(get_db)],
    progress: Annotated[Progress, Depends(get_or_create_progress)],
):
    """Submit a choice; return updated stats (risk_score, level, total_attempted, correct_count, current_streak)."""
    scenario = db.query(Scenario).filter(Scenario.id == body.scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    choices_data = json.loads(scenario.choices_json)
    if body.choice_index < 0 or body.choice_index >= len(choices_data):
        raise HTTPException(status_code=400, detail="Invalid choice")
    choice = choices_data[body.choice_index]
    is_safe = choice["is_safe"]
    score_delta = choice["score_delta"]

    progress.risk_score = apply_score_delta(progress.risk_score, score_delta)
    progress.total_attempted += 1
    if is_safe:
        progress.correct_count += 1
        progress.current_streak = getattr(progress, "current_streak", 0) + 1
    else:
        progress.current_streak = 0
    db.add(Attempt(
        progress_id=progress.id,
        scenario_id=scenario.id,
        choice_index=body.choice_index,
        is_safe=is_safe,
        tactic=scenario.tactic,
    ))
    db.commit()
    db.refresh(progress)

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
def get_stats(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    progress: Annotated[Progress, Depends(get_or_create_progress)],
):
    """Get current stats: risk_score, level, tactic breakdown, tips, current_streak, safe_percentage, achievements."""
    rows = (
        db.query(Attempt.tactic, func.count(Attempt.id).label("cnt"))
        .filter(Attempt.progress_id == progress.id, Attempt.is_safe == False)
        .group_by(Attempt.tactic)
        .all()
    )
    tactic_breakdown = [TacticBreakdownSchema(tactic=t, mistake_count=c) for t, c in rows]
    all_tactics = ["Urgency", "Authority", "Scarcity", "Reciprocity", "Fear"]
    by_tactic = {t.tactic: t.mistake_count for t in tactic_breakdown}
    tactic_breakdown = [TacticBreakdownSchema(tactic=t, mistake_count=by_tactic.get(t, 0)) for t in all_tactics]
    tips = get_tips_for_weak_tactics(tactic_breakdown, max_tips=3)
    level = compute_level(progress.risk_score)
    safe_pct = (progress.correct_count / progress.total_attempted * 100) if progress.total_attempted else 0.0
    achievements = compute_achievements(progress, list(progress.attempts))
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
