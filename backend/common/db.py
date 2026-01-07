"""Database utilities and connection management for PostgreSQL."""

from typing import AsyncGenerator

from pydantic import Field
from pydantic_settings import BaseSettings
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class DatabaseSettings(BaseSettings):
    """Database settings loaded from environment variables."""
    
    postgres_dsn: str = Field(
        default="postgresql+asyncpg://parlonacore:parlonacore@localhost:5432/parlonacore",
        description="PostgreSQL connection URL.",
        validation_alias="POSTGRES_DSN",
    )
    run_db_migrations: bool = Field(
        default=False,
        description="Whether to run database migrations on startup.",
        validation_alias="RUN_DB_MIGRATIONS",
    )

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
db_settings = DatabaseSettings()


# Create async engine
engine = create_async_engine(
    db_settings.postgres_dsn,
    echo=False,  # Set to True for SQL debugging
    pool_pre_ping=True,
    pool_recycle=300,
)


# Create async session maker
SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI to get database session."""
    async with SessionLocal() as session:
        yield session