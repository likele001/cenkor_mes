import json
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.system_version import SystemVersion


def get_latest_version(db: Session) -> SystemVersion | None:
    return db.scalar(
        select(SystemVersion).order_by(SystemVersion.release_date.desc()).limit(1)
    )


def list_versions(db: Session, offset: int = 0, limit: int = 200) -> list[SystemVersion]:
    return list(
        db.scalars(
            select(SystemVersion)
            .order_by(SystemVersion.release_date.desc())
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