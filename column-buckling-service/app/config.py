"""运行期配置，均可由环境变量覆盖。"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    # SQLAlchemy 异步驱动地址。
    # 容器内默认连接 compose 附带的 PostgreSQL；测试环境通过环境变量覆盖为 SQLite。
    database_url: str = (
        "postgresql+asyncpg://buckling:buckling@db:5432/buckling"
    )

    # 历史查询分页。
    default_history_limit: int = 50
    max_history_limit: int = 200

    # 数值比较相对容差：控制模式归类、“回到欧拉/屈服”的贴合判定都用它。
    relative_tolerance: float = 1e-9

    # 单次批量核算的最大组数。
    max_batch_items: int = 1000


settings = Settings()
