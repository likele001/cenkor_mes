"""Seed 脚本：为 CRM 预置常用字典（胜负原因等）。

使用方式：
    python -m scripts.seed_crm_dictionaries           # 直接执行（默认写入所有租户）
    # 或在 Python 内
    from app.database import SessionLocal
    from scripts.seed_crm_dictionaries import run
    with SessionLocal() as db:
        run(db, tenant_id=1)

该脚本支持幂等：若 reason 已存在（按 tenant_id + type + name 判重）则跳过。
"""
from __future__ import annotations

from typing import Iterable

WIN_REASONS: list[str] = [
    "价格有竞争力",
    "产品功能领先",
    "服务响应快",
    "方案契合度",
    "客户关系深度",
]

LOSS_REASONS: list[str] = [
    "价格过高",
    "预算不足",
    "竞品A",
    "客户选择竞品",
    "功能不满足",
    "服务响应慢",
    "未接触关键决策人",
    "项目延期",
    "内部组织变动",
    "其他",
]


def _upsert_win_loss_reasons(
    db,
    tenant_id: int,
    type_value: str,
    reasons: Iterable[str],
) -> int:
    """向指定租户写入一组 win/loss 原因，返回实际新增条数。"""
    import app.crud.crm as _crm
    list_fn = getattr(_crm, "list_win_loss_reasons", None)
    create_fn = getattr(_crm, "create_win_loss_reason", None)
    if not callable(list_fn) or not callable(create_fn):
        # 底层 crud 尚未实现，跳过
        return 0

    existing_names: set[str] = set()
    existing = list_fn(db, tenant_id=tenant_id, type=type_value)
    for item in existing or []:
        name = getattr(item, "name", None)
        if name:
            existing_names.add(str(name).strip())

    inserted = 0
    for reason in reasons:
        name = str(reason).strip()
        if not name or name in existing_names:
            continue
        try:
            create_fn(db, tenant_id=tenant_id, type=type_value, name=name, is_active=True)
            inserted += 1
            existing_names.add(name)
        except Exception:
            # 唯一键冲突等异常直接跳过
            continue
    return inserted


def run(db, tenant_id: int | None = None) -> dict:
    """主入口：写入预置的 win/loss 原因。

    Args:
        db: SQLAlchemy Session
        tenant_id: 目标租户 ID；若为 None，则遍历当前系统中所有租户写入。

    Returns:
        dict 形如 {"tenant_id": {...}, "total_inserted": N}
    """
    # 延迟导入，避免脚本环境缺包时直接挂掉
    from sqlalchemy import select

    try:
        from app.models.tenant import Tenant  # type: ignore
    except Exception:
        Tenant = None  # type: ignore

    if tenant_id is not None:
        tenant_ids = [int(tenant_id)]
    else:
        if Tenant is None:
            return {"error": "Tenant 模型不可用，请显式传入 tenant_id"}
        tenant_ids = [r[0] for r in db.execute(select(Tenant.id).order_by(Tenant.id.asc())).all()]

    per_tenant: dict[int, dict] = {}
    total_wins = 0
    total_losses = 0
    for tid in tenant_ids:
        try:
            wins = _upsert_win_loss_reasons(db, tenant_id=tid, type_value="win", reasons=WIN_REASONS)
            losses = _upsert_win_loss_reasons(db, tenant_id=tid, type_value="loss", reasons=LOSS_REASONS)
            db.commit()
            per_tenant[tid] = {"win": wins, "loss": losses}
            total_wins += wins
            total_losses += losses
        except Exception:
            db.rollback()
            per_tenant[tid] = {"error": True}
            continue

    return {
        "total_inserted": total_wins + total_losses,
        "total_wins": total_wins,
        "total_losses": total_losses,
        "per_tenant": per_tenant,
    }


if __name__ == "__main__":  # pragma: no cover - CLI
    import sys

    try:
        from app.database import SessionLocal  # type: ignore
    except Exception as exc:
        print(f"[seed_crm_dictionaries] 无法加载数据库 Session：{exc}", file=sys.stderr)
        sys.exit(1)

    target_tenant_id: int | None = None
    for arg in sys.argv[1:]:
        if arg.startswith("--tenant-id="):
            target_tenant_id = int(arg.split("=", 1)[1])

    with SessionLocal() as session:
        result = run(session, tenant_id=target_tenant_id)

    print(f"[seed_crm_dictionaries] 完成：{result['total_inserted']} 条新增。")
    print(f"  - win  原因：{result['total_wins']}")
    print(f"  - loss 原因：{result['total_losses']}")
    if len(result["per_tenant"]) <= 10:
        for tid, info in result["per_tenant"].items():
            print(f"  - tenant_id={tid}: {info}")
