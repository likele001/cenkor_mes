"""飞书/企微 settings 旧结构 → 新 channels 嵌套结构 一次性迁移

旧结构 (例 飞书)：
{
  "groups": [
    {"code": "production", "name": "生产群", "chat_id": "oc_xxx", "webhook_url": "https://...", "enabled": true}
  ]
}

新结构 (飞书 + 企微合并后)：
{
  "groups": [
    {
      "code": "production",
      "name": "生产群",
      "enabled": true,
      "channels": {
        "feishu": {"chat_id": "oc_xxx", "enabled": true},
        "wecom":  {"webhook_url": "https://...", "enabled": true}
      }
    }
  ]
}

迁移策略：
- 飞书 settings 读到旧结构（顶层有 chat_id/webhook_url 字段）时，转换并写回
- 企微 settings 读到旧结构（顶层有 webhook_url 字段）时，转换并写回
- 已迁移（顶层是 channels）跳过，幂等
- 迁移记录写入迁移历史
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud.tenant_setting import get_setting, upsert_setting

logger = logging.getLogger(__name__)

FEISHU_KEY = "feishu.notify"
WECOM_KEY = "wecom.notify"
MIGRATION_FLAG_KEY = "notify_migration.v2"


def _migrate_group_channels(group: dict) -> dict:
    """将旧结构（顶层 chat_id / webhook_url）转 channels 嵌套"""
    if "channels" in group and isinstance(group.get("channels"), dict):
        return group  # 已迁移

    new_group = {
        "code": group.get("code", ""),
        "name": group.get("name", group.get("code", "")),
        "enabled": group.get("enabled", True),
        "channels": {
            "feishu": {
                "chat_id": group.get("chat_id", ""),
                "enabled": bool((group.get("chat_id") or "").strip()),
            },
            "wecom": {
                "webhook_url": group.get("webhook_url", ""),
                "enabled": bool((group.get("webhook_url") or "").strip()),
            },
            "dingtalk": {
                "webhook_url": "",
                "webhook_secret": "",
                "enabled": False,
            },
        },
    }
    return new_group


def _ensure_dingtalk_channel(group: dict) -> dict:
    if "channels" not in group or not isinstance(group.get("channels"), dict):
        return group
    channels = group["channels"]
    if "dingtalk" not in channels:
        channels["dingtalk"] = {"webhook_url": "", "webhook_secret": "", "enabled": False}
    return group


def _is_old_structure(value: str | None) -> bool:
    """判断 settings 是否仍是旧结构（顶层 group 包含 chat_id/webhook_url）"""
    if not value:
        return False
    try:
        data = json.loads(value)
    except Exception:
        return False
    for g in data.get("groups") or []:
        if "chat_id" in g or "webhook_url" in g:
            return True
    return False


def _is_new_structure(value: str | None) -> bool:
    """判断 settings 是否是新 channels 结构"""
    if not value:
        return False
    try:
        data = json.loads(value)
    except Exception:
        return False
    for g in data.get("groups") or []:
        if "channels" in g and isinstance(g["channels"], dict):
            return True
    return False


def _migrate_settings(db: Session) -> dict:
    """迁移飞书 + 企微 settings，返回迁移结果摘要"""
    result = {"feishu": "skipped", "wecom": "skipped"}

    feishu_row = get_setting(db, FEISHU_KEY)
    if _is_old_structure(feishu_row.value if feishu_row else None):
        try:
            data = json.loads(feishu_row.value)
            data["groups"] = [_migrate_group_channels(g) for g in data.get("groups") or []]
            upsert_setting(db, key=FEISHU_KEY, value=json.dumps(data, ensure_ascii=False))
            result["feishu"] = "migrated"
        except Exception as e:
            logger.exception("feishu migration failed: %s", e)
            result["feishu"] = f"failed:{e}"
    elif _is_new_structure(feishu_row.value if feishu_row else None):
        try:
            data = json.loads(feishu_row.value)
            patched = [_ensure_dingtalk_channel(g) for g in data.get("groups") or []]
            if patched != data.get("groups"):
                data["groups"] = patched
                upsert_setting(db, key=FEISHU_KEY, value=json.dumps(data, ensure_ascii=False))
                result["feishu"] = "patched_dingtalk"
            else:
                result["feishu"] = "already_new"
        except Exception as e:
            logger.exception("feishu dingtalk patch failed: %s", e)
            result["feishu"] = "already_new"
    else:
        result["feishu"] = "empty"

    wecom_row = get_setting(db, WECOM_KEY)
    if _is_old_structure(wecom_row.value if wecom_row else None):
        try:
            data = json.loads(wecom_row.value)
            data["groups"] = [_migrate_group_channels(g) for g in data.get("groups") or []]
            upsert_setting(db, key=WECOM_KEY, value=json.dumps(data, ensure_ascii=False))
            result["wecom"] = "migrated"
        except Exception as e:
            logger.exception("wecom migration failed: %s", e)
            result["wecom"] = f"failed:{e}"
    elif _is_new_structure(wecom_row.value if wecom_row else None):
        try:
            data = json.loads(wecom_row.value)
            patched = [_ensure_dingtalk_channel(g) for g in data.get("groups") or []]
            if patched != data.get("groups"):
                data["groups"] = patched
                upsert_setting(db, key=WECOM_KEY, value=json.dumps(data, ensure_ascii=False))
                result["wecom"] = "patched_dingtalk"
            else:
                result["wecom"] = "already_new"
        except Exception as e:
            logger.exception("wecom dingtalk patch failed: %s", e)
            result["wecom"] = "already_new"
    else:
        result["wecom"] = "empty"

    return result


def run_migration(db: Session) -> dict:
    """迁移飞书 + 企微 settings；幂等；记录到 migrate log"""
    r = _migrate_settings(db)
    upsert_setting(
        db,
        key=MIGRATION_FLAG_KEY,
        value=json.dumps({"at": __import__("datetime").datetime.utcnow().isoformat()}, ensure_ascii=False),
    )
    db.commit()
    return {"result": r}
