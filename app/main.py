"""Social Engineering Simulator - FastAPI app entry point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import engine, AsyncSessionLocal
from app.routers import web, api, auth
from app.services.seeding import seed_scenarios


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ✅ create tables (async)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # ✅ seed scenarios (async)
    async with AsyncSessionLocal() as db:
        await seed_scenarios(db)

    yield
    # shutdown if needed


app = FastAPI(
    title="Social Engineering Simulator",
    description="Training against social engineering (MVP)",
    lifespan=lifespan,
)

settings = get_settings()

# Mount static files at /static
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(web.router)
app.include_router(auth.router)
app.include_router(api.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
