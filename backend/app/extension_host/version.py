# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""扩展/核心版本号比较（semver 的够用实现）。"""
from __future__ import annotations

import re

_SEMVER_RE = re.compile(
    r"^v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:-(?P<pre>[0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$"
)


def parse_version(value: str | None) -> tuple[int, int, int] | None:
    """解析 ``1.2.3`` / ``v1.2.3`` / ``1.2.3-rc.1``；非法返回 None。"""
    if not value:
        return None
    m = _SEMVER_RE.match(str(value).strip())
    if not m:
        return None
    return int(m.group("major")), int(m.group("minor")), int(m.group("patch"))


def is_semver(value: str | None) -> bool:
    return parse_version(value) is not None


def compare_versions(a: str | None, b: str | None) -> int:
    """a>b 返回 1，a<b 返回 -1，相等/不可比返回 0。"""
    pa, pb = parse_version(a), parse_version(b)
    if pa is None or pb is None:
        return 0
    return (pa > pb) - (pa < pb)


def is_newer(latest: str | None, installed: str | None) -> bool:
    """严格大于才算可升级；缺值/非法版本不下判断。"""
    pa, pb = parse_version(latest), parse_version(installed)
    if pa is None or pb is None:
        return False
    return pa > pb


def meets_min_version(current: str | None, minimum: str | None) -> bool:
    """current >= minimum；minimum 为空表示不限制。"""
    if not minimum:
        return True
    pc, pm = parse_version(current), parse_version(minimum)
    if pc is None or pm is None:
        return False
    return pc >= pm


def read_core_version() -> str:
    """读取仓库根 ``VERSION``（缺失时退回 0.0.0，激活上报不再为空）。"""
    from pathlib import Path

    for parent in Path(__file__).resolve().parents:
        candidate = parent / "VERSION"
        if candidate.is_file():
            try:
                return candidate.read_text(encoding="utf-8").strip() or "0.0.0"
            except OSError:
                break
    return "0.0.0"
