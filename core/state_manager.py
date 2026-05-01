"""Async state persistence via SQLAlchemy + SQLite (aiosqlite).

Entity id convention: ``{org_path}/{skill_id}/{instance_id}`` (string, enforced by callers).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from config.settings import Settings, load_settings


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class StateRecord(Base):
    """One row per ``entity_id``; last write wins."""

    __tablename__ = "skill_state"

    entity_id: Mapped[str] = mapped_column(String(2048), primary_key=True)
    state_data: Mapped[dict[str, Any]] = mapped_column(SQLiteJSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    skill_id: Mapped[str] = mapped_column(String(512), nullable=False)


class StateManager:
    """Async CRUD for Skill state blobs (audit: ``updated_at`` + ``skill_id``)."""

    def __init__(
        self,
        database_url: str | None = None,
        *,
        settings: Settings | None = None,
    ) -> None:
        url = database_url
        if url is None:
            url = (settings or load_settings()).database_url
        self._database_url = url
        self._engine: AsyncEngine = create_async_engine(
            url,
            echo=False,
        )
        self._session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self._engine,
            expire_on_commit=False,
        )

    async def init_schema(self) -> None:
        """Create tables if missing (call once at startup / in tests)."""
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def save_state(
        self,
        entity_id: str,
        state: dict[str, Any],
        skill_id: str,
    ) -> None:
        """Upsert JSON state; records ``skill_id`` and ``updated_at`` for audit."""
        now = _utc_now()
        payload = dict(state)
        async with self._session_factory() as session:
            row = await session.get(StateRecord, entity_id)
            if row is None:
                session.add(
                    StateRecord(
                        entity_id=entity_id,
                        state_data=payload,
                        updated_at=now,
                        skill_id=skill_id,
                    ),
                )
            else:
                row.state_data = payload
                row.skill_id = skill_id
                row.updated_at = now
            await session.commit()

    async def get_state(self, entity_id: str) -> dict[str, Any] | None:
        """Return a shallow copy of stored JSON, or None if missing."""
        async with self._session_factory() as session:
            row = await session.get(StateRecord, entity_id)
            if row is None:
                return None
            return dict(row.state_data)

    async def aclose(self) -> None:
        await self._engine.dispose()

    async def __aenter__(self) -> StateManager:
        await self.init_schema()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()
