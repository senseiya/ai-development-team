from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from src.core.config import settings

# Create the SQLAlchemy engine. 
# For SQLite, we use 'check_same_thread=False' to allow multiple threads to access the same connection,
# which is necessary for FastAPI's asynchronous nature.
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)

# SessionLocal is a factory for creating new database sessions.
# Each request to the FastAPI application will get its own session.
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Session:
    """
    Dependency provider for database sessions.

    Yields a new SQLAlchemy session for each request and ensures it is closed
    after the request is completed.

    Returns:
        Session: A SQLAlchemy session instance.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """
    Utility function to create all database tables defined in the models.
    This should be called during application startup or via a migration tool.
    """
    import models  # Local import to avoid circular dependencies
    models.Base.metadata.create_all(bind=engine)