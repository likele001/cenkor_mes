# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""云存储配置管理接口。

- 读取一律走脱敏视图，凭据明文永不外泄。
- 保存/清空凭据、激活 provider、连通性测试、本地备份开关。
- 业务校验失败（未知 provider、未配置凭据即激活）转 BizError(400)。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.admin.system.common import write_op_log
from app.core.deps import get_current_user, get_db, require_permissions
from app.core.errors import BizError
from app.core.response import ok
from app.models.user import User
from app.schemas.cloud_storage import ActivateIn, CloudCredsIn, SettingsIn
from app.services import cloud_storage_config as svc
from app.storage.factory import registered_drivers


router = APIRouter(dependencies=[Depends(require_permissions(["cloud_storage.manage"]))])


def _bad_request(exc: ValueError) -> BizError:
    return BizError(400, str(exc))


@router.get("")
def get_config(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """脱敏配置视图 + 系统已注册的存储驱动。"""
    view = svc.get_masked_view(db)
    view["supported_drivers"] = registered_drivers()
    return ok(view)


@router.put("/providers/{provider}/credentials")
def save_credentials(
    provider: str,
    payload: CloudCredsIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """合并式保存凭据（掩码/空字段保留原值）。"""
    try:
        cfg = svc.update_credentials(db, provider, payload.to_dict(), user_id=user.id)
    except ValueError as exc:
        raise _bad_request(exc) from exc
    write_op_log(
        db, request, user,
        module="system.cloud_storage", action="save_credentials",
        object_type="cloud_storage_config", object_id=cfg.id, detail=provider,
    )
    db.commit()
    return ok(svc.get_masked_view(db))


@router.delete("/providers/{provider}/credentials")
def clear_credentials(
    provider: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        cfg = svc.clear_credentials(db, provider, user_id=user.id)
    except ValueError as exc:
        raise _bad_request(exc) from exc
    write_op_log(
        db, request, user,
        module="system.cloud_storage", action="clear_credentials",
        object_type="cloud_storage_config", object_id=cfg.id, detail=provider,
    )
    db.commit()
    return ok(svc.get_masked_view(db))


@router.post("/providers/{provider}/activate")
def activate_provider(
    provider: str,
    payload: ActivateIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """切换激活 provider；云 provider 必须已配置凭据。路径与体均可提供 provider，以路径为准。"""
    target = provider or payload.provider
    try:
        cfg = svc.activate(db, target, user_id=user.id)
    except ValueError as exc:
        raise _bad_request(exc) from exc
    write_op_log(
        db, request, user,
        module="system.cloud_storage", action="activate",
        object_type="cloud_storage_config", object_id=cfg.id, detail=target,
    )
    db.commit()
    return ok(svc.get_masked_view(db))


@router.post("/providers/{provider}/test")
def test_provider(
    provider: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """连通性测试：按已存凭据构造驱动并探测（local 恒 ok）。异常不外抛，返回 ok=False。"""
    from app.storage.factory import build_storage

    storage = build_storage(provider, db=db)
    if hasattr(storage, "health_check"):
        return ok(storage.health_check())
    # 降级到 local（凭据不全/SDK 缺失）时没有 health_check
    return ok({"ok": storage.driver == "local", "provider": storage.driver, "detail": {"fell_back_to_local": storage.driver == "local" and provider != "local"}})


@router.put("/settings")
def update_settings(
    payload: SettingsIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cfg = svc.set_keep_local_backup(db, payload.keep_local_backup, user_id=user.id)
    write_op_log(
        db, request, user,
        module="system.cloud_storage", action="update_settings",
        object_type="cloud_storage_config", object_id=cfg.id,
        detail=f"keep_local_backup={cfg.keep_local_backup}",
    )
    db.commit()
    return ok(svc.get_masked_view(db))
