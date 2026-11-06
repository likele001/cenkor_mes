# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
import json
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.system_version import SystemVersion

# 仓库根：backend/app/crud -> 上溯 3 级；与 upgrade_service.py 的 ROOT 保持同一位置
ROOT = Path(__file__).resolve().parents[3]
VERSION_FILE = ROOT / "VERSION"


def read_local_version() -> str:
    """读 VERSION 文件；任何异常返回空串，由调用方回退。

    这里不复用 upgrade_service.read_local_version()，避免一个轻量的版本查询
    API 反向依赖 2000+ 行、带 subprocess/git 副作用的升级模块。
    """
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return ""


def _version_order():
    """开发日志排序口径：发布日期降序；同一天连发多个版本时用自增 id 兜底。

    CHANGELOG.json 按发布先后顺序写入，sync_changelog_from_file 顺序插入，
    因此 id 越大版本越新。只按 release_date 排序时，同日并列返回哪条由
    数据库执行计划决定（MySQL 8 实测返回 id 最小的一条），会显示成旧版本。
    """
    return SystemVersion.release_date.desc(), SystemVersion.id.desc()


def get_latest_version(db: Session) -> SystemVersion | None:
    return db.scalar(
        select(SystemVersion).order_by(*_version_order()).limit(1)
    )


def get_current_version(db: Session) -> SystemVersion | None:
    """当前系统版本 = 实际运行的 VERSION 文件所对应的那条记录。

    口径说明：/admin/system/version 展示的是「当前运行的构建版本」，不是
    「开发日志里发布日期最新的一条」。后者在一天内连发多个版本时会并列，
    且若 CHANGELOG 里存在未发布版本也会取错。精确匹配不到时（例如全新
    安装、首次启动尚未 seed）回退到 get_latest_version()。
    """
    ver = read_local_version()
    if ver:
        row = get_version_by_number(db, ver)
        if row is not None:
            return row
    return get_latest_version(db)


def list_versions(db: Session, offset: int = 0, limit: int = 200) -> list[SystemVersion]:
    return list(
        db.scalars(
            select(SystemVersion)
            .order_by(*_version_order())
            .offset(offset)
            .limit(limit)
        ).all()
    )


def get_version_by_number(db: Session, version: str) -> SystemVersion | None:
    return db.scalar(select(SystemVersion).where(SystemVersion.version == version))


def create_version(
    db: Session,
    version: str,
    release_date: date,
    description: str,
) -> SystemVersion:
    obj = SystemVersion(version=version, release_date=release_date, description=description)
    db.add(obj)
    db.flush()
    return obj


def sync_changelog_from_file(db: Session, changelog_path: Path) -> int:
    """从 CHANGELOG.json 同步版本日志（按版本号幂等，跳过已存在的）。返回新增条数。"""
    if not changelog_path.exists():
        return 0
    try:
        rows = json.loads(changelog_path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    existing = set(db.scalars(select(SystemVersion.version)).all())
    added = 0
    for row in rows:
        ver = row.get("version")
        if not ver or ver in existing:
            continue
        try:
            rel_date = date.fromisoformat(str(row.get("release_date", "")))
        except ValueError:
            continue
        create_version(db, ver, rel_date, str(row.get("description", "")))
        existing.add(ver)
        added += 1
    if added:
        db.commit()
    return added
