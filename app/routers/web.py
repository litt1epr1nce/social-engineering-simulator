"""Web routes: home, train, result, reset. Jinja2 templates."""
import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import verify_session_token
from app.db.session import get_db
from app.models.user import User
from app.models.progress import Progress
from app.models.scenario import Scenario
from app.models.attempt import Attempt
from app.schemas.scenario import ChoiceSchema
from app.schemas.stats import TacticBreakdownSchema
from app.services.scoring import (
    INITIAL_RISK_SCORE,
    TACTIC_DISPLAY_RU,
    apply_score_delta,
    compute_level,
    compute_achievements,
    get_level_display_ru,
    get_tactic_display_ru,
    get_tips_for_weak_tactics,
)

router = APIRouter()
settings = get_settings()
templates = Jinja2Templates(directory="app/templates")


# ---------- helpers ----------

async def get_current_user_optional(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User | None:
    token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        return None
    user_id = verify_session_token(token)
    if user_id is None:
        return None
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


def get_or_create_session_id(request: Request) -> str:
    sid = request.cookies.get(settings.session_cookie_name)
    if not sid:
        sid = str(uuid.uuid4())
    return sid


async def get_or_create_progress(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
) -> Progress:
    if current_user:
        result = await db.execute(
            select(Progress).where(Progress.user_id == current_user.id)
        )
        progress = result.scalar_one_or_none()
        if progress is None:
            progress = Progress(
                user_id=current_user.id,
                session_id=None,
                risk_score=INITIAL_RISK_SCORE,
                total_attempted=0,
                correct_count=0,
                current_streak=0,
            )
            db.add(progress)
            await db.commit()
            await db.refresh(progress)
        return progress

    sid = get_or_create_session_id(request)
    result = await db.execute(
        select(Progress).where(Progress.session_id == sid)
    )
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


def _ensure_session_cookie(request: Request, response: Response, progress: Progress) -> None:
    if progress.session_id and not request.cookies.get(settings.session_cookie_name):
        response.set_cookie(
            key=settings.session_cookie_name,
            value=progress.session_id,
            max_age=settings.session_cookie_max_age,
            httponly=True,
            samesite="lax",
        )


# ---------- routes ----------

@router.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
    progress: Annotated[Progress, Depends(get_or_create_progress)],
):
    level_display_ru = get_level_display_ru(progress.risk_score) if progress else None
    mini_stats = None
    if progress and progress.total_attempted > 0:
        mini_stats = {
            "risk_score": progress.risk_score,
            "level_display_ru": level_display_ru,
            "current_streak": getattr(progress, "current_streak", 0),
        }

    resp = templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "current_user": current_user,
            "is_guest": current_user is None,
            "mini_stats": mini_stats,
        },
    )
    _ensure_session_cookie(request, resp, progress)
    return resp


@router.get("/train", response_class=HTMLResponse)
async def train_get(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
    progress: Annotated[Progress, Depends(get_or_create_progress)],
):
    result = await db.execute(
        select(Scenario).order_by(func.random()).limit(1)
    )
    scenario = result.scalar_one_or_none()
    if not scenario:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "message": "Нет доступных сценариев. Запустите приложение снова.",
                "current_user": current_user,
                "is_guest": current_user is None,
            },
            status_code=404,
        )

    choices = [ChoiceSchema(**c) for c in json.loads(scenario.choices_json)]
    resp = templates.TemplateResponse(
        "train.html",
        {
            "request": request,
            "current_user": current_user,
            "is_guest": current_user is None,
            "scenario": scenario,
            "choices": choices,
            "current_streak": getattr(progress, "current_streak", 0),
            "tactic_display_ru": TACTIC_DISPLAY_RU,
        },
    )
    _ensure_session_cookie(request, resp, progress)
    return resp


@router.post("/train", response_class=RedirectResponse)
async def train_post(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    progress: Annotated[Progress, Depends(get_or_create_progress)],
    scenario_id: Annotated[int, Form()],
    choice_index: Annotated[int, Form()],
):
    result = await db.execute(
        select(Scenario).where(Scenario.id == scenario_id)
    )
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    choices_data = json.loads(scenario.choices_json)
    if choice_index < 0 or choice_index >= len(choices_data):
        raise HTTPException(status_code=400, detail="Invalid choice")

    choice = choices_data[choice_index]
    is_safe = choice["is_safe"]
    score_delta = choice["score_delta"]

    progress.risk_score = apply_score_delta(progress.risk_score, score_delta)
    progress.total_attempted += 1
    if is_safe:
        progress.correct_count += 1
        progress.current_streak = getattr(progress, "current_streak", 0) + 1
    else:
        progress.current_streak = 0

    db.add(
        Attempt(
            progress_id=progress.id,
            scenario_id=scenario.id,
            choice_index=choice_index,
            is_safe=is_safe,
            tactic=scenario.tactic,
        )
    )
    await db.commit()

    response = RedirectResponse(
        request.url_for("train_feedback").include_query_params(
            scenario_id=scenario_id,
            choice_index=choice_index,
        ),
        status_code=303,
    )
    _ensure_session_cookie(request, response, progress)
    return response


@router.get("/train/feedback", response_class=HTMLResponse)
async def train_feedback(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
    scenario_id: int,
    choice_index: int,
):
    result = await db.execute(
        select(Scenario).where(Scenario.id == scenario_id)
    )
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    choices_data = json.loads(scenario.choices_json)
    if choice_index < 0 or choice_index >= len(choices_data):
        raise HTTPException(status_code=400, detail="Invalid choice")

    choice = choices_data[choice_index]
    return templates.TemplateResponse(
        "train_feedback.html",
        {
            "request": request,
            "current_user": current_user,
            "is_guest": current_user is None,
            "scenario": scenario,
            "choice": choice,
            "is_safe": choice["is_safe"],
            "explanation": choice["explanation"],
            "tactic": scenario.tactic,
            "tactic_display_ru": get_tactic_display_ru(scenario.tactic),
        },
    )


@router.get("/result", response_class=HTMLResponse)
async def result_get(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
    progress: Annotated[Progress, Depends(get_or_create_progress)],
):
    result = await db.execute(
        select(Attempt.tactic, func.count(Attempt.id).label("cnt"))
        .where(Attempt.progress_id == progress.id, Attempt.is_safe == False)  # noqa
        .group_by(Attempt.tactic)
    )
    rows = result.all()

    tactic_breakdown = [TacticBreakdownSchema(tactic=t, mistake_count=c) for t, c in rows]
    all_tactics = ["Urgency", "Authority", "Scarcity", "Reciprocity", "Fear"]
    by_tactic = {t.tactic: t.mistake_count for t in tactic_breakdown}
    tactic_breakdown = [
        TacticBreakdownSchema(tactic=t, mistake_count=by_tactic.get(t, 0))
        for t in all_tactics
    ]

    tips = get_tips_for_weak_tactics(tactic_breakdown, max_tips=3)
    level = compute_level(progress.risk_score)
    level_display_ru = get_level_display_ru(progress.risk_score)
    safe_pct = (progress.correct_count / progress.total_attempted * 100) if progress.total_attempted else 0.0

    attempts_result = await db.execute(
        select(Attempt).where(Attempt.progress_id == progress.id).order_by(Attempt.id)
    )
    attempts = attempts_result.scalars().all()
    achievements = compute_achievements(progress, attempts)

    resp = templates.TemplateResponse(
        "result.html",
        {
            "request": request,
            "current_user": current_user,
            "is_guest": current_user is None,
            "risk_score": progress.risk_score,
            "level": level,
            "level_display_ru": level_display_ru,
            "total_attempted": progress.total_attempted,
            "correct_count": progress.correct_count,
            "safe_percentage": round(safe_pct, 1),
            "current_streak": getattr(progress, "current_streak", 0),
            "tactic_breakdown": tactic_breakdown,
            "tactic_display_ru": TACTIC_DISPLAY_RU,
            "tips": tips,
            "achievements": achievements,
        },
    )
    _ensure_session_cookie(request, resp, progress)
    return resp


@router.post("/reset", response_class=RedirectResponse)
async def reset_post(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    progress: Annotated[Progress, Depends(get_or_create_progress)],
):
    await db.execute(
        select(Attempt).where(Attempt.progress_id == progress.id).delete()
    )
    progress.risk_score = INITIAL_RISK_SCORE
    progress.total_attempted = 0
    progress.correct_count = 0
    progress.current_streak = 0
    await db.commit()

    response = RedirectResponse(request.url_for("home"), status_code=303)
    _ensure_session_cookie(request, response, progress)
    return response
