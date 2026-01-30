"""Scenario model: one training scenario with channel, tactic, choices (JSON)."""
from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.session import Base

# SQLite doesn't have native JSON; we use Text and store JSON string
# PostgreSQL can use JSON/JSONB later


class Scenario(Base):
    __tablename__ = "scenarios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    channel = Column(String(32), nullable=False)  # email | messenger | call
    message_text = Column(Text, nullable=False)
    tactic = Column(String(64), nullable=False)  # Urgency, Authority, Scarcity, Reciprocity, Fear
    # choices: JSON array of {text, is_safe, explanation, score_delta}
    choices_json = Column(Text, nullable=False)

    attempts = relationship("Attempt", back_populates="scenario")
