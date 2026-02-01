"""Auth routes: login, register, logout. Session-based auth via secure cookie."""
from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    hash_password,
    verify_password,
    create_session_token,
    verify_session_token,
)
from app.db.session import get_db
from app.models.user import User
from app.models.progress import Progress

router = APIRouter()
settings = get_settings()
templates = Jinja2Templates(directory="app/templates")

# Простая, практичная проверка email
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _redirect(url, **params) -> RedirectResponse:
    """303 redirect with query params."""
    return RedirectResponse(url.include_query_params(**params), status_code=303)


def _normalize_email(email: str | None) -> str:
    return (email or "").strip().lower()


def get_current_user_optional(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> User | None:
    """Return current user if auth cookie is valid; else None."""
    token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        return None

    user_id = verify_session_token(token)
    if user_id is None:
        return None

    return db.query(User).filter(User.id == user_id).first()


@router.get("/login", response_class=HTMLResponse)
def login_get(
    request: Request,
    current_user: Annotated["User | None", Depends(get_current_user_optional)],
    error: str | None = None,
):
    """Show login form."""
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "current_user": current_user,
            "is_guest": current_user is None,
            "error": error,
        },
    )


@router.post("/login", response_class=RedirectResponse)
def login_post(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
):
    """Authenticate and set auth cookie; redirect to home."""
    email_norm = _normalize_email(email)

    user = db.query(User).filter(User.email == email_norm).first()
    if not user or not verify_password(password, user.hashed_password):
        return _redirect(request.url_for("login_get"), error="invalid")

    token = create_session_token(user.id)
    response = RedirectResponse(request.url_for("home"), status_code=303)
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=settings.auth_cookie_max_age,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return response


@router.get("/register", response_class=HTMLResponse)
def register_get(
    request: Request,
    current_user: Annotated["User | None", Depends(get_current_user_optional)],
    link_progress: int = 0,
    error: str | None = None,
):
    """Show register form. link_progress=1 when coming from 'Save progress to account'."""
    return templates.TemplateResponse(
        "register.html",
        {
            "request": request,
            "current_user": current_user,
            "is_guest": current_user is None,
            "link_progress": link_progress,
            "error": error,
        },
    )


@router.post("/register", response_class=RedirectResponse)
def register_post(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    link_progress: Annotated[int, Form()] = 0,
):
    """Create user, optionally link guest progress, set auth cookie."""
    email_norm = _normalize_email(email)
    pwd = password or ""

    # email format
    if not email_norm or not EMAIL_RE.match(email_norm):
        return _redirect(request.url_for("register_get"), link_progress=link_progress, error="email")

    # minimum password length (characters)
    if len(pwd) < 8:
        return _redirect(request.url_for("register_get"), link_progress=link_progress, error="short")

    # bcrypt hard limit: 72 bytes (UTF-8)
    if len(pwd.encode("utf-8")) > 72:
        return _redirect(request.url_for("register_get"), link_progress=link_progress, error="toolong")

    # user exists?
    if db.query(User).filter(User.email == email_norm).first():
        return _redirect(request.url_for("register_get"), link_progress=link_progress, error="exists")

    # create user
    user = User(email=email_norm, hashed_password=hash_password(pwd))
    db.add(user)
    db.commit()
    db.refresh(user)

    # link guest progress
    if link_progress:
        sid = request.cookies.get(settings.session_cookie_name)
        if sid:
            progress = db.query(Progress).filter(Progress.session_id == sid).first()
            if progress:
                progress.user_id = user.id
                progress.session_id = None
                db.commit()

    # auto-login
    token = create_session_token(user.id)
    response = RedirectResponse(request.url_for("result_get"), status_code=303)
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=settings.auth_cookie_max_age,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return response


@router.post("/logout", response_class=RedirectResponse)
def logout_post(request: Request):
    """Clear auth cookie and redirect to home."""
    response = RedirectResponse(request.url_for("home"), status_code=303)
    # ВАЖНО: path должен совпадать с тем, что ставили в set_cookie()
    response.delete_cookie(settings.auth_cookie_name, path="/")
    return response
