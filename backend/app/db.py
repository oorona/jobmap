"""Operational state lives here; vector_search also persists the current job corpus."""
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from sqlalchemy import DateTime, Float, Integer, MetaData, String, text, select, delete
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from .config import DB_URL

SQLITE = str(DB_URL).startswith('sqlite')


def now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    metadata = MetaData(schema=None if SQLITE else 'jev')


class Usage(Base):
    __tablename__ = 'usage'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created: Mapped[float] = mapped_column(Float, index=True)
    amount: Mapped[float] = mapped_column(Float)
    state: Mapped[str] = mapped_column(String(16), default='reserved')


class Session(Base):
    __tablename__ = 'sessions'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires: Mapped[float] = mapped_column(Float, index=True)
    active_until: Mapped[float] = mapped_column(Float, default=0)


class Rate(Base):
    __tablename__ = 'rates'
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    window: Mapped[int] = mapped_column(Integer)
    count: Mapped[int] = mapped_column(Integer)


engine = create_async_engine(DB_URL, pool_pre_ping=True, **({'connect_args': {'timeout': 30}} if SQLITE else {'pool_size': 5, 'max_overflow': 5}))
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def transaction():
    async with SessionLocal() as db:
        try:
            if SQLITE:
                await db.execute(text('BEGIN IMMEDIATE'))
            else:
                await db.execute(text('SELECT pg_advisory_xact_lock(721903)'))
            yield db
            await db.commit()
        except BaseException:
            await db.rollback()
            raise


async def init_db():
    if SQLITE:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
