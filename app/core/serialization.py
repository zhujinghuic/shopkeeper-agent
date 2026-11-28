"""
查询结果序列化工具

MySQL 驱动会把 DECIMAL 列（包括 SUM(INT) 的结果）返回成 Decimal，
datetime/date 返回成日期对象。这些对象既不能直接写进 JSON 列，
也不能被 json.dumps 处理，会抛
"Object of type Decimal is not JSON serializable"。
统一在这里做一次转换，SSE 回传和会话落库都复用。
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any


def to_jsonable(value: Any) -> Any:
    """把单个值转换成可 JSON 序列化的基础类型"""

    if isinstance(value, Decimal):
        # 整数值转成 int，避免页面上出现 1.0 这种不自然的展示
        if value == value.to_integral_value() and abs(value) < 10**15:
            return int(value)
        return float(value)

    if isinstance(value, datetime):
        return value.isoformat(sep=" ")

    if isinstance(value, (date, time)):
        return value.isoformat()

    if isinstance(value, timedelta):
        return str(value)

    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8", errors="ignore")

    return value


def rows_to_jsonable(rows: list[dict]) -> list[dict]:
    """把整行结果转换成可 JSON 序列化的字典列表"""

    return [{key: to_jsonable(item) for key, item in row.items()} for row in rows]
