"""Social Engineering Simulator - FastAPI app entry point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.core.config import get_settings
from app.db.session import engine
from app.db.base import Base
from app.routers import web, api
from app.services.seeding import seed_scenarios
from app.db.session import SessionLocal


def create_tables():
    Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    db = SessionLocal()
    try:
        seed_scenarios(db)
    finally:
        db.close()
    yield
    # shutdown if needed
    pass


app = FastAPI(
    title="Social Engineering Simulator",
    description="Training against social engineering (MVP)",
    lifespan=lifespan,
)

settings = get_settings()

# Mount static files at /static
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(web.router)
app.include_router(api.router)


@app.get("/health")
def health():
    return {"status": "ok"}
