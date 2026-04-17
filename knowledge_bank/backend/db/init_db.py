from backend.db.base import Base
from backend.db.session import get_engine
from backend.models import cohort_signal, knowledge_unit, source  # noqa: F401


def init_db(drop_existing: bool = False) -> None:
    engine = get_engine()
    if drop_existing:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
