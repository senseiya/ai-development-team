from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# Create the SQLAlchemy Base class for ORM models
Base = declarative_base()

# Create the engine
# 'check_same_thread': False is required for SQLite when using multiple threads (FastAPI/Uvicorn)
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
)

# Create a configured "Session" class and add it to the application
# The sessionmaker will provide a new Session object for each database request
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db():
    """
    Dependency provider for a database session.
    Yields a new SQLAlchemy session for each request and ensures it is closed 
    after the request is completed.

    Yields:
        SessionLocal: A SQLAlchemy session instance.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initializes the database by creating all tables defined via the Base class.
    This should be called during application startup.
    """
    Base.metadata.create_all(bind=engine)