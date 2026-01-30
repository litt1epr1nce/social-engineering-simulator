"""Pydantic schemas for stats and results."""
from pydantic import BaseModel


class TacticBreakdownSchema(BaseModel):
    tactic: str
    mistake_count: int


class TipSchema(BaseModel):
    tactic: str
    tip: str


class AchievementSchema(BaseModel):
    id: str
    name_ru: str
    unlocked: bool


class StatsOutSchema(BaseModel):
    risk_score: int
    level: str
    total_attempted: int
    correct_count: int
    tactic_breakdown: list[TacticBreakdownSchema]
    tips: list[TipSchema]
    current_streak: int = 0
    safe_percentage: float = 0.0
    achievements: list[AchievementSchema] | None = None
