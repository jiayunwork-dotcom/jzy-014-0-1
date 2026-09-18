"""异步数据库引擎与会话管理。

默认 PostgreSQL（compose）；测试通过环境变量
``DATABASE_URL=sqlite+aiosqlite://`` 覆盖为内存 SQLite。
每请求一个会话，请求级互不相干，保证并发下历史不乱串。
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings


def _engine_kwargs(url: str) -> dict:
    if url.startswith("sqlite"):
        # 文件库放宽写锁等待，便于并发请求串行化写入而不是立刻报错。
        return {"future": True, "connect_args": {"timeout": 30}}
    # PostgreSQL：启用连接池，保持健康检查。
    return {
        "future": True,
        "pool_size": 5,
        "max_overflow": 10,
        "pool_pre_ping": True,
    }


engine = create_async_engine(settings.database_url, **_engine_kwargs(settings.database_url))

# SQLite 内存库用 StaticPool 让所有连接共享同一个内存数据库。
if settings.database_url in ("sqlite+aiosqlite://", "sqlite://"):
    from sqlalchemy.pool import StaticPool

    engine = create_async_engine(
        settings.database_url,
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def init_db() -> None:
    """建表（幂等）。应用启动时调用。"""
    from app.models import Base  #  noqa: WPS433 - 确保模型已注册

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose_db() -> None:
    await engine.dispose()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：提供请求级会话并保证关闭。"""
    async with AsyncSessionLocal() as session:
        yield session
