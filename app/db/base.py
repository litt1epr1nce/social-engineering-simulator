"""SQLAlchemy declarative base and model imports for Alembic."""
from app.db.session import Base

# Import all models so Alembic can see them
from app.models.attempt import Attempt  # noqa: F401
from app.models.progress import Progress  # noqa: F401
from app.models.scenario import Scenario  # noqa: F401
from app.models.user import User  # noqa: F401

__all__ = ["Base", "User", "Scenario", "Progress", "Attempt"]
