"""Progress model: one per guest session or per user. Tracks risk score and counts."""
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from app.db.session import Base


class Progress(Base):
    __tablename__ = "progress"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # For guest: unique session_id (UUID string). For user: null and we use user_id.
    session_id = Column(String(64), unique=True, nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    risk_score = Column(Integer, nullable=False, default=50)  # 0-100
    total_attempted = Column(Integer, nullable=False, default=0)
    correct_count = Column(Integer, nullable=False, default=0)
    current_streak = Column(Integer, nullable=False, default=0)  # consecutive safe decisions

    user = relationship("User", back_populates="progress")
    attempts = relationship("Attempt", back_populates="progress", order_by="Attempt.id")
