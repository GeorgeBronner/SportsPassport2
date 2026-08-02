from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from sports_passport.core.config import settings

# Create SQLAlchemy engine
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {}
)

if "sqlite" in settings.database_url:
    # WAL allows concurrent readers alongside a writer; busy_timeout makes a
    # second writer (e.g. two admin imports, or parallel backfill scripts)
    # wait for the lock instead of failing immediately with "database is
    # locked". Documented as already-decided in docs/SP3_plan.md's risk table but
    # never actually wired up until now.
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models. DeclarativeBase (SQLAlchemy 2.0) rather than
# declarative_base(): the latter returns an untyped class, which makes every
# Mapped[] annotation on a model invisible to a type checker.
class Base(DeclarativeBase):
    pass


def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
