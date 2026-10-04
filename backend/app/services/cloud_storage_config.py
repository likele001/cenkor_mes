# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""云存储配置服务：凭据密文入库、读取脱敏、provider 激活校验。

- 凭据以 JSON 明文经 AES-256-GCM 加密后存入 cloud_storage_config.creds_<provider>。
- 对外读取一律脱敏（secret_key 全遮、access_key 首尾保留）。
- 激活非 local provider 前必须已配置凭据。
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.cloud_storage import CloudStorageConfig
from app.storage import crypto

# 支持的 provider（local 恒可用；云 provider 需配置凭据）
PROVIDERS: tuple[str, ...] = ("local", "aliyun", "tencent", "qiniu", "upyun")
CLOUD_PROVIDERS: tuple[str, ...] = ("aliyun", "tencent", "qiniu", "upyun")

# 读取时全遮的敏感字段
_FULL_MASK_FIELDS = {"secret_key", "access_key_secret", "sk"}
# 读取时部分脱敏字段
_PARTIAL_MASK_FIELDS = {"access_key", "ak"}


def _col(provider: str) -> str:
    return f"creds_{provider}"


def get_or_create(db: Session) -> CloudStorageConfig:
    """获取全局配置单行，不存在则创建（active=local）。"""
    cfg = db.scalar(select(CloudStorageConfig).order_by(CloudStorageConfig.id).limit(1))
    if cfg is None:
        cfg = CloudStorageConfig(active_provider="local")
        db.add(cfg)
        db.flush()
    return cfg


def set_credentials(db: Session, provider: str, creds: dict[str, Any], user_id: int | None = None) -> CloudStorageConfig:
    """加密并写入某 provider 的凭据。"""
    if provider not in PROVIDERS:
        raise ValueError(f"未知 provider: {provider}")
    cfg = get_or_create(db)
    token = crypto.encrypt(json.dumps(creds, ensure_ascii=False))
    setattr(cfg, _col(provider), token)
    cfg.updated_by = user_id
    db.flush()
    return cfg


def update_credentials(db: Session, provider: str, incoming: dict[str, Any], user_id: int | None = None) -> CloudStorageConfig:
    """合并式更新凭据：仅覆盖非空且非掩码占位的字段，保留未改动（如回显为 •••• 的密钥）的原值。"""
    if provider not in PROVIDERS:
        raise ValueError(f"未知 provider: {provider}")
    existing = get_credentials(db, provider)
    merged = dict(existing)
    for k, v in (incoming or {}).items():
        if v is None:
            continue
        if isinstance(v, str) and (not v.strip() or "•" in v):
            continue  # 空值或掩码占位，保留原值
        merged[k] = v
    return set_credentials(db, provider, merged, user_id=user_id)


def clear_credentials(db: Session, provider: str, user_id: int | None = None) -> CloudStorageConfig:
    """清空某 provider 凭据；若其为当前激活项则回退 local。"""
    if provider not in PROVIDERS:
        raise ValueError(f"未知 provider: {provider}")
    cfg = get_or_create(db)
    setattr(cfg, _col(provider), None)
    if cfg.active_provider == provider and provider != "local":
        cfg.active_provider = "local"
    cfg.updated_by = user_id
    db.flush()
    return cfg


def get_credentials(db: Session, provider: str) -> dict[str, Any]:
    """解密返回某 provider 明文凭据（内部使用，未配置返回空 dict）。"""
    if provider not in PROVIDERS:
        return {}
    cfg = get_or_create(db)
    token = getattr(cfg, _col(provider), None)
    if not token:
        return {}
    try:
        data = json.loads(crypto.decrypt(token))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001 - 解密/解析失败视为未配置
        return {}


def is_configured(db: Session, provider: str) -> bool:
    cfg = get_or_create(db)
    return bool(getattr(cfg, _col(provider), None))


def activate(db: Session, provider: str, user_id: int | None = None) -> CloudStorageConfig:
    """切换激活 provider；云 provider 必须已配置凭据。"""
    if provider not in PROVIDERS:
        raise ValueError(f"未知 provider: {provider}")
    if provider != "local" and not is_configured(db, provider):
        raise ValueError(f"provider {provider} 尚未配置凭据，无法激活")
    cfg = get_or_create(db)
    cfg.active_provider = provider
    cfg.updated_by = user_id
    db.flush()
    return cfg


def set_keep_local_backup(db: Session, enabled: bool, user_id: int | None = None) -> CloudStorageConfig:
    cfg = get_or_create(db)
    cfg.keep_local_backup = bool(enabled)
    cfg.updated_by = user_id
    db.flush()
    return cfg


def _mask_creds(creds: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in creds.items():
        if k in _FULL_MASK_FIELDS:
            out[k] = "•" * 8 if v else ""
        elif k in _PARTIAL_MASK_FIELDS:
            out[k] = crypto.mask(str(v))
        else:
            out[k] = v
    return out


def get_masked_view(db: Session) -> dict[str, Any]:
    """对外配置视图：激活项 + 各 provider 是否已配置 + 脱敏凭据。"""
    cfg = get_or_create(db)
    providers: dict[str, Any] = {}
    for p in PROVIDERS:
        creds = get_credentials(db, p)
        providers[p] = {
            "configured": is_configured(db, p),
            "credentials": _mask_creds(creds) if creds else {},
        }
    return {
        "active_provider": cfg.active_provider,
        "keep_local_backup": cfg.keep_local_backup,
        "providers": providers,
    }
