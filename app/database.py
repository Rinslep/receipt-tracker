from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.config import settings

engine = create_async_engine(
    settings.database_url,
    # SQLite needs check_same_thread=False; ignored by other drivers
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
