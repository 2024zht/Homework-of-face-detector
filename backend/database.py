"""SQLAlchemy async database setup"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from config import DATABASE_URL, SYNC_DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def _migrate_checkin_correction_columns(conn):
    """Add correction tracking columns to checkins table if missing (SQLite-safe)."""
    from sqlalchemy import text
    # Check existing columns
    result = await conn.execute(text("PRAGMA table_info(checkins)"))
    existing = [row[1] for row in result.fetchall()]
    if "original_user_id" not in existing:
        await conn.execute(text("ALTER TABLE checkins ADD COLUMN original_user_id INTEGER REFERENCES users(id)"))
    if "corrected_by" not in existing:
        await conn.execute(text("ALTER TABLE checkins ADD COLUMN corrected_by INTEGER REFERENCES users(id)"))
    if "corrected_at" not in existing:
        await conn.execute(text("ALTER TABLE checkins ADD COLUMN corrected_at DATETIME"))


async def init_db():
    """Create all tables and seed default data."""
    from models import User, Location, CheckIn, QRSession  # noqa
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Run migration for new columns (idempotent)
        await _migrate_checkin_correction_columns(conn)

    async with async_session() as session:
        from models import User, Location
        from sqlalchemy import select
        import bcrypt, config

        # Default admin
        result = await session.execute(select(User).where(User.username == "admin"))
        if result.scalar_one_or_none() is None:
            session.add(User(
                username="admin",
                password_hash=bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode(),
                name="系统管理员", role="admin", is_active=True,
            ))

        # Default lab location
        loc_result = await session.execute(select(Location).where(Location.name == config.DEFAULT_LAB_NAME))
        if loc_result.scalar_one_or_none() is None:
            session.add(Location(
                name=config.DEFAULT_LAB_NAME,
                latitude=config.DEFAULT_LAB_LAT,
                longitude=config.DEFAULT_LAB_LNG,
                radius_meters=100,
                created_by=1,
            ))

        # Test student user
        test_result = await session.execute(select(User).where(User.username == "gxf"))
        if test_result.scalar_one_or_none() is None:
            session.add(User(
                username="gxf",
                password_hash=bcrypt.hashpw("123456".encode(), bcrypt.gensalt()).decode(),
                name="郭晓飞", role="student", is_active=True,
            ))

        await session.commit()
