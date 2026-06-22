from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from provereno.config import settings
from provereno.models import Base

engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
