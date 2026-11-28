"""
SQL 安全校验（执行白名单）

模型生成的 SQL 不可信：它可能被话术诱导成多语句、DDL/DML、跨库读 information_schema，
也可能拖着一条百万行的全表扫描回来。所以真正的边界不能写在提示词里，要在执行前拦。

这一层用 AST 而不是正则：正则会被注释拼接、大小写变形、换行写法绕过，
而 AST 能精确判断语句类型、引用了哪些表、调用了哪些函数。

它只回答"能不能执行"，不判断业务语义对不对；语法可执行性仍然交给 explain。
"""

import re
from dataclasses import dataclass

import sqlglot
from sqlglot import exp

# 没有显式 LIMIT 时补上的行数上限，防止一次全表扫描把服务和数据库一起拖慢
DEFAULT_ROW_LIMIT = 500

# 这些库保存数据库自身的元信息，允许查询等于允许把整个库结构拖走
# 一条合法的 SELECT 就能读它们，所以必须按库名单独拦
FORBIDDEN_SCHEMAS = {"information_schema", "mysql", "performance_schema", "sys"}

# 拖库、打挂数据库、加锁阻塞的经典函数
FORBIDDEN_FUNCTIONS = {"sleep", "benchmark", "load_file", "get_lock", "release_lock"}

# 顶层语句只允许查询：UNION / INTERSECT / EXCEPT 也是查询，不能误杀
QUERY_STATEMENTS = (exp.Select, exp.Union, exp.Intersect, exp.Except)

# 去掉字符串字面量、标识符反引号和注释后的文本，用于在解析前做兜底关键字判断
_LITERAL_PATTERN = re.compile(
    r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"|`[^`]*`|--[^\n]*|#[^\n]*|/\*.*?\*/",
    re.S,
)
# INTO OUTFILE 部分方言解析器直接报错，先按文本兜一下，让拦截原因更准确
_INTO_FILE_PATTERN = re.compile(r"\binto\s+(?:out|dump)file\b", re.I)


def strip_literals(sql: str) -> str:
    """去掉字符串、反引号和注释，只留语句骨架"""

    return _LITERAL_PATTERN.sub(" ", sql)


@dataclass
class GuardResult:
    """一次安全校验的结论

    sql 可能和入参不同：补 LIMIT 或收紧 LIMIT 时会返回改写后的语句，
    调用方必须用 result.sql 去执行，否则改写等于没做。
    """

    allowed: bool
    sql: str
    rule: str = ""
    reason: str = ""

    def as_dict(self) -> dict:
        """给 state 和审计表用的扁平结构"""

        return {
            "allowed": self.allowed,
            "rule": self.rule,
            "reason": self.reason,
        }


def allowed_tables_from_infos(table_infos) -> list[str]:
    """从召回结果里取本次允许查询的表名，作为白名单"""

    names: list[str] = []
    for info in table_infos or []:
        name = (
            info.get("name") if isinstance(info, dict) else getattr(info, "name", None)
        )
        if name:
            names.append(str(name))
    return names


def guard_sql(
    sql: str,
    allowed_tables: list[str] | None = None,
    row_limit: int = DEFAULT_ROW_LIMIT,
) -> GuardResult:
    """按执行白名单校验一条 SQL

    allowed_tables 为空表示不做表白名单限制（例如单元测试），
    非空时任何不在名单里的表都会被拒——这能挡住模型去查没召回的表。
    """

    text = (sql or "").strip()
    if not text:
        return GuardResult(False, text, "empty", "SQL 为空")

    if _INTO_FILE_PATTERN.search(strip_literals(text)):
        return GuardResult(
            False, text, "into_outfile", "禁止 SELECT ... INTO OUTFILE / DUMPFILE"
        )

    try:
        statements = [item for item in sqlglot.parse(text, read="mysql") if item]
    except Exception as e:
        # 解析不了就无法证明它安全，按拒绝处理，不给"可能没问题"留口子
        return GuardResult(False, text, "parse", f"SQL 解析失败，无法确认安全性：{e}")

    if len(statements) != 1:
        # "select 1; delete from t" 会被解析成两条，必须在这里拦下
        return GuardResult(
            False,
            text,
            "multi_statement",
            f"只允许单条语句，实际解析出 {len(statements)} 条",
        )

    stmt = statements[0]

    if not isinstance(stmt, QUERY_STATEMENTS):
        return GuardResult(
            False,
            text,
            "not_select",
            f"只允许 SELECT 查询，当前语句类型是 {stmt.key.upper()}",
        )

    if stmt.find(exp.Into):
        return GuardResult(
            False, text, "into_outfile", "禁止 SELECT ... INTO OUTFILE / DUMPFILE"
        )

    if stmt.args.get("locks"):
        return GuardResult(False, text, "lock", "禁止 FOR UPDATE 等加锁查询")

    allowed = {str(name).lower() for name in allowed_tables or []}
    for table in _iter_tables(stmt):
        schema = (table.db or "").lower()
        if schema in FORBIDDEN_SCHEMAS:
            return GuardResult(
                False,
                text,
                "system_schema",
                f"禁止访问系统库：{schema}.{table.name}",
            )
        if allowed and table.name.lower() not in allowed:
            return GuardResult(
                False,
                text,
                "table_not_allowed",
                f"表 {table.name} 不在本次召回的候选表范围内",
            )

    for func in stmt.find_all(exp.Func):
        name = _function_name(func)
        if name in FORBIDDEN_FUNCTIONS:
            return GuardResult(
                False, text, "forbidden_function", f"禁止调用函数 {name.upper()}"
            )

    return _apply_row_limit(stmt, text, row_limit)


def _iter_tables(stmt):
    """遍历真实表引用，跳过 CTE 名

    WITH order_stats AS (...) 里的 order_stats 不是表，如果不去掉，
    会被表白名单误判成"查了不在召回范围内的表"。
    """

    cte_names = {cte.alias_or_name.lower() for cte in stmt.find_all(exp.CTE)}
    for table in stmt.find_all(exp.Table):
        name = (table.name or "").lower()
        if not name or name in cte_names:
            continue
        yield table


def _function_name(func) -> str:
    """取函数名，兼容 MySQL 方言下解析成 Anonymous 的函数（SLEEP、BENCHMARK 等）"""

    if isinstance(func, exp.Anonymous):
        return (func.name or "").lower()
    return (func.sql_name() or "").lower()


def _apply_row_limit(stmt, text: str, row_limit: int) -> GuardResult:
    """保证查询有 LIMIT，且不超过上限

    没有 LIMIT 就补上；写了 LIMIT 但超过上限就收紧。
    LIMIT 是变量或表达式时不动它，避免把正确 SQL 改坏。
    """

    limit_node = stmt.args.get("limit")
    if limit_node is None:
        guarded = stmt.limit(row_limit)
        return GuardResult(
            True,
            guarded.sql(dialect="mysql"),
            "limit_added",
            f"未指定 LIMIT，已自动限制为 {row_limit} 行",
        )

    value = limit_node.expression
    if isinstance(value, exp.Literal) and value.is_int:
        if int(value.this) > row_limit:
            guarded = stmt.limit(row_limit)
            return GuardResult(
                True,
                guarded.sql(dialect="mysql"),
                "limit_capped",
                f"LIMIT {value.this} 超过上限，已收紧为 {row_limit} 行",
            )

    return GuardResult(True, text)
