"""Attempt model: one user choice for one scenario; stores tactic for breakdown."""
from sqlalchemy import Column, Integer, Boolean, String, ForeignKey
from sqlalchemy.orm import relationship

from app.db.session import Base


class Attempt(Base):
    __tablename__ = "attempts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    progress_id = Column(Integer, ForeignKey("progress.id"), nullable=False, index=True)
    scenario_id = Column(Integer, ForeignKey("scenarios.id"), nullable=False, index=True)
    choice_index = Column(Integer, nullable=False)  # 0-based index into scenario choices
    is_safe = Column(Boolean, nullable=False)
    tactic = Column(String(64), nullable=False)  # denormalized for breakdown by tactic

    progress = relationship("Progress", back_populates="attempts")
    scenario = relationship("Scenario", back_populates="attempts")
