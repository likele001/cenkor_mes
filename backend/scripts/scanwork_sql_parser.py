"""解析 scanwork 导出的 INSERT 语句（参考文件.sql）"""

from __future__ import annotations

import re
from typing import Any


def _split_sql_row(inner: str) -> list[Any]:
    """解析单行 VALUES 括号内内容，支持引号与 NULL。"""
    values: list[Any] = []
    buf: list[str] = []
    in_str = False
    i = 0
    while i < len(inner):
        ch = inner[i]
        if in_str:
            if ch == "'" and i + 1 < len(inner) and inner[i + 1] == "'":
                buf.append("'")
                i += 2
                continue
            if ch == "'":
                values.append("".join(buf))
                buf = []
                in_str = False
                i += 1
                continue
            buf.append(ch)
            i += 1
            continue
        if ch == "'":
            in_str = True
            i += 1
            continue
        if ch.isspace() or ch == ",":
            if buf:
                token = "".join(buf).strip()
                if token.upper() == "NULL":
                    values.append(None)
                else:
                    try:
                        values.append(int(token))
                    except ValueError:
                        try:
                            values.append(float(token))
                        except ValueError:
                            values.append(token)
                buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    if buf:
        token = "".join(buf).strip()
        if token.upper() == "NULL":
            values.append(None)
        else:
            try:
                values.append(int(token))
            except ValueError:
                try:
                    values.append(float(token))
                except ValueError:
                    values.append(token)
    return values


def parse_insert_rows(sql_text: str, table: str) -> list[list[Any]]:
    pattern = rf"INSERT INTO `{table}`\s*\([^)]+\)\s*VALUES\s*(.*?);"
    m = re.search(pattern, sql_text, re.DOTALL | re.IGNORECASE)
    if not m:
        return []
    block = m.group(1).strip()
    rows: list[list[Any]] = []
    depth = 0
    start = -1
    for i, ch in enumerate(block):
        if ch == "(":
            if depth == 0:
                start = i + 1
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0 and start >= 0:
                rows.append(_split_sql_row(block[start:i]))
                start = -1
    return rows
