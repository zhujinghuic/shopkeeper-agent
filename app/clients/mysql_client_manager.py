"""
MySQL 客户端管理器

统一创建和管理项目中的异步 MySQL 客户端，当前项目会同时连接三套 MySQL
meta 库存放结构化元数据，dw 库模拟教学数仓，chat 库存放多轮会话记录
后两者和 meta 分开是有意的：元数据可以由脚本随时重建，会话记录不行
模块对外提供可复用的客户端管理器和 session 工厂
方便脚本入口 服务层和仓储层按统一方式访问数据库
"""

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from app.conf.app_config import DBConfig, app_config


class MySQLClientManager:
    """管理 MySQL Engine 和 Session 工厂"""

    def __init__(self, config: DBConfig):
        # Engine 是数据库连接层核心对象，底层会维护连接池
        self.engine: AsyncEngine | None = None
        # session_factory 用来按需创建新的 AsyncSession
        self.session_factory = None
        # 保存数据库配置，后面拼接连接地址要用
        self.config = config

    def _get_url(self) -> str:
        """
        拼接 MySQL 异步连接地址
        mysql+asyncmy 表示：连接 MySQL，并使用 asyncmy 作为异步驱动
        """
        return f"mysql+asyncmy://{self.config.user}:{self.config.password}@{self.config.host}:{self.config.port}/{self.config.database}?charset=utf8mb4"

    def init(self):
        """初始化 Engine 和 Session 工厂"""
        # 创建异步 Engine，相当于先把“数据库连接能力”准备好
        self.engine = create_async_engine(
            self._get_url(), pool_size=10, pool_pre_ping=True
        )
        # 基于 Engine 创建 Session 工厂，后面真正查库时再拿 session
        self.session_factory = async_sessionmaker(
            self.engine, autoflush=True, expire_on_commit=False
        )

    async def close(self):
        """释放连接池资源"""
        await self.engine.dispose()


# 三套连接各管一类数据：元数据、数仓、会话记录
# 后续由不同 repository 按职责分别使用
meta_mysql_client_manager = MySQLClientManager(app_config.db_meta)
dw_mysql_client_manager = MySQLClientManager(app_config.db_dw)
chat_mysql_client_manager = MySQLClientManager(app_config.db_chat)

if __name__ == "__main__":
    dw_mysql_client_manager.init()

    async def test():
        """执行一次简单查询，验证 MySQL 连接与结果结构"""
        async with dw_mysql_client_manager.session_factory() as session:
            sql = "select * from fact_order limit 10"
            result = await session.execute(text(sql))
            # mappings().fetchall() 会把结果转成“按列名访问”的行对象列表
            rows = result.mappings().fetchall()
            print(type(rows))
            print(type(rows[0]))
            print(rows[0]["order_id"])

    asyncio.run(test())
