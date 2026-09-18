"""pytest 公共夹具。

在导入任何 app 模块之前把数据库指向内存 SQLite（StaticPool 共享单连接），
每个用例前清空历史表，保证并发/历史类断言互不干扰。
"""

import os
import tempfile

# 必须在导入 app.config / app.database 之前设置。
# 用文件型 SQLite：测试 HTTP 客户端（ASGITransport 上的并发任务）与
# 夹具清理各自持有连接，需要多连接才能真实验证“并发互不串扰”。
_DB_PATH = os.path.join(tempfile.gettempdir(), "buckling_pytest.db")
if os.path.exists(_DB_PATH):
    os.remove(_DB_PATH)
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_DB_PATH}")

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.database import AsyncSessionLocal, engine, init_db  # noqa: E402
from app.models import Base  # noqa: E402


@pytest_asyncio.fixture
async def client():
    # 内存库按需建表，并清空历史。
    await init_db()
    async with AsyncSessionLocal() as session:
        await session.execute(text("DELETE FROM calculation_records"))
        await session.commit()

    transport = ASGITransport(app=_app())
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: Base.metadata.drop_all(sync_conn))


def _app():
    from app.main import app

    return app
