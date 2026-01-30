"""Pydantic schemas for scenarios and choices."""
from pydantic import BaseModel, Field


class ChoiceSchema(BaseModel):
    text: str
    is_safe: bool
    explanation: str
    score_delta: int  # e.g. -5 for correct, +10 for wrong


class ScenarioOutSchema(BaseModel):
    id: int
    title: str
    channel: str
    message_text: str
    tactic: str
    choices: list[ChoiceSchema]

    class Config:
        from_attributes = True


class ScenarioSubmitSchema(BaseModel):
    scenario_id: int
    choice_index: int = Field(ge=0)
