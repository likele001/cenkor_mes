# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""功能市场 API：连接 Cenkor 门户 hub（admin.cenkor.cn），按产品拉取应用目录 /
已购授权，一键下载安装扩展（热生效，无需重启）。

对接协议（hub 侧全部挂在 /api/v1/store 前缀）：
- 设备码绑定：POST public/cloud/device/start → 用户在 portal.cenkor.cn/connect 确认
  → POST public/cloud/device/poll 换发长期 instance_token（Bearer）。
- 已购：GET cloud/my-purchases（Bearer）→ 每项含 license_key。
- 可购目录：GET apps?product=cenkormes（公开）。
- 激活绑定：POST licenses/{license_key}/activate（instance_fp）。
- 下载：GET cloud/packages/{app_key}?license_key=（zip）。
- 解绑：POST cloud/instance/revoke-self（Bearer）。
"""
from __future__ import annotations

import hashlib
import json
import logging
import shutil
import threading
import uuid
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.extension_host.host import (
    extensions_base_dir,
    hot_setup_extension,
    hot_teardown_extension,
)
from app.extension_host.lifecycle import (
    LifecycleError,
    backup_target,
    install_or_update,
    preflight,
    stage,
    swap,
    lifecycle_logs,
    repair,
    rollback,
    set_enabled,
    uninstall,
    use_base,
)
from app.extension_host.loader import scan_extensions
from app.extension_host.state import runtime
from app.models.platform_setting import PlatformSetting

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/market", tags=["admin-market"])

# 本产品标识：向 hub 上报，用于多产品目录隔离
PRODUCT = "cenkormes"

# 连接配置 key（存入 platform_settings）
HUB_URL_KEY = "market_hub_url"
INSTANCE_UID_KEY = "market_instance_uid"
INSTANCE_TOKEN_KEY = "market_instance_token"
ACCOUNT_KEY = "market_account"
# 设备码绑定的临时态（poll 成功后清理）
BIND_DEVICE_CODE_KEY = "market_bind_device_code"

# 授权到期自动停用的周期刷新间隔（分钟）；<=0 关闭（仅靠打开市场页时手动刷新）
ENTITLEMENT_SYNC_MINUTES = 15


# ── Schemas ──────────────────────────────────────────────────────────────────

class HubIn(BaseModel):
    hub_url: str = Field(min_length=1, max_length=512)


class InstallIn(BaseModel):
    app_key: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]{1,63}$")
    allow_downgrade: bool = False


class UninstallIn(BaseModel):
    app_key: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]{1,63}$")
    purge: bool = False
    confirm_key: str = ""


# 生命周期动作统一要求 setting.manage（安装/卸载/启停/回滚/修复/清除都是高危操作）
_LIFECYCLE_MGMT = [Depends(require_permissions(["setting.manage"]))]


# ── 配置读写 helpers ─────────────────────────────────────────────────────────

def _get_setting(db: Session, key: str) -> str:
    row = db.execute(select(PlatformSetting).where(PlatformSetting.key == key)).scalar_one_or_none()
    return row.value if row else ""


def _set_setting(db: Session, key: str, value: str) -> None:
    row = db.execute(select(PlatformSetting).where(PlatformSetting.key == key)).scalar_one_or_none()
    if row:
        row.value = value
    else:
        db.add(PlatformSetting(key=key, value=value))
    db.commit()


def _clear_setting(db: Session, key: str) -> None:
    row = db.execute(select(PlatformSetting).where(PlatformSetting.key == key)).scalar_one_or_none()
    if row:
        db.delete(row)
        db.commit()


TOKEN_ENC_PREFIX = "enc:v1:"


def _set_instance_token(db: Session, token: str) -> None:
    """实例令牌加密入库（AES-256-GCM，密钥派生自 JWT_SECRET）。"""
    if not token:
        _clear_setting(db, INSTANCE_TOKEN_KEY)
        return
    from app.storage.crypto import encrypt

    _set_setting(db, INSTANCE_TOKEN_KEY, TOKEN_ENC_PREFIX + (encrypt(token) or ""))


def _get_instance_token(db: Session) -> str:
    """读实例令牌；历史明文行在首次读取时透明迁移为密文。"""
    from app.storage.crypto import decrypt

    raw = _get_setting(db, INSTANCE_TOKEN_KEY)
    if not raw:
        return ""
    if not raw.startswith(TOKEN_ENC_PREFIX):
        try:
            _set_instance_token(db, raw)
        except Exception as e:  # noqa: BLE001 - 迁移失败不影响本次使用
            logger.warning("market.instance_token_encrypt_failed: %s", e)
        return raw
    try:
        return decrypt(raw[len(TOKEN_ENC_PREFIX):])
    except Exception as e:  # noqa: BLE001 - 换过 JWT_SECRET 且无 OLD 密钥时解不开
        logger.warning("market.instance_token_decrypt_failed: %s", e)
        return ""


def _hub_url(db: Session) -> str:
    return _get_setting(db, HUB_URL_KEY).rstrip("/")


def _normalize_hub_url(raw: str) -> str:
    """校验并归一化 hub 地址。

    这不是一条普通文本配置：`_store_url` 把它的每个出站请求都带上 instance token /
    license_key，所以它是**出站信任锚** —— 谁能写这个值，谁就能把实例凭据引到自己的
    服务器上，再伪装成 hub 下发扩展包。约束：协议只允许 http/https、不许带
    userinfo / query / fragment、主机必须命中白名单（`MARKET_HUB_ALLOWED_HOSTS`，
    逗号分隔，按域后缀匹配，`*` 表示不限制）。
    """
    value = (raw or "").strip().rstrip("/")
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail=f"hub 地址协议须为 http/https，收到「{parts.scheme or '空'}」")
    if not parts.hostname:
        raise HTTPException(status_code=400, detail="hub 地址缺少主机名")
    if parts.username or parts.password:
        raise HTTPException(status_code=400, detail="hub 地址不允许携带用户名/密码")
    if parts.query or parts.fragment:
        raise HTTPException(status_code=400, detail="hub 地址不允许携带查询参数或锚点")
    host = parts.hostname.lower()
    allowed = [h.strip().lower().lstrip(".") for h in settings.MARKET_HUB_ALLOWED_HOSTS.split(",") if h.strip()]
    if "*" not in allowed and not any(host == d or host.endswith(f".{d}") for d in allowed):
        raise HTTPException(
            status_code=400,
            detail=(
                f"hub 主机「{host}」不在白名单内（当前允许：{', '.join(allowed) or '（空）'}）。"
                "确需接入其他 hub 请在 .env 追加 MARKET_HUB_ALLOWED_HOSTS"
            ),
        )
    return value


def _instance_uid(db: Session) -> str:
    """本机稳定实例 UID：首次访问时生成并持久化，用于设备码绑定与实例指纹。"""
    uid = _get_setting(db, INSTANCE_UID_KEY)
    if not uid:
        uid = f"cenkormes-{uuid.uuid4().hex[:16]}"
        _set_setting(db, INSTANCE_UID_KEY, uid)
    return uid


def _instance_url(request: Request) -> str:
    """尽量拿到本实例对外地址（scheme+host），供 hub 展示与授权域名绑定。"""
    base = str(request.base_url or "").rstrip("/")
    return base[:255]


def _store_url(db: Session, path: str) -> str:
    hub = _hub_url(db)
    if not hub:
        raise HTTPException(status_code=400, detail="尚未配置 hub 地址，请先在功能市场设置 hub URL")
    return f"{hub}/api/v1/store/{path.lstrip('/')}"


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── 市场概况（供 /status 展示）────────────────────────────────────────────────

# 最近一次授权快照同步的结果：True=hub 可达且快照已刷新；False=请求失败/非 200；
# None=本进程还没同步过（刚重启、或未绑定 hub）。/status 用它报「hub 是否可达」，
# 自己不发消息——市场页加载即调 /status，不能被 15s 的 hub 超时拖住。
_LAST_SYNC_OK: bool | None = None


def _ver_tuple(v: str) -> tuple[int, ...]:
    """取版本号的数字段：'1.0.10'->(1,0,10)、'v1.2'->(1,2)、'1.0.1-rc2'->(1,0,1)。"""
    head = str(v or "").strip().lstrip("vV")
    cut = len(head)
    for i, ch in enumerate(head):
        if not (ch.isdigit() or ch == "."):
            cut = i
            break
    return tuple(int(x) for x in head[:cut].split(".") if x.isdigit())


def _is_newer(latest: str, installed: str) -> bool:
    """latest 严格新于 installed 才算「可更新」。

    任一为空、或补零比较后仍相等都不算——缺值即放行在这里反着用作「缺值即不提示」：
    老 hub 不返回 latest_version 时，页面应当安静，不该催用户升级。
    """
    if not latest or not installed:
        return False
    a, b = _ver_tuple(latest), _ver_tuple(installed)
    if not a or not b:
        return False
    n = max(len(a), len(b))
    return (a + (0,) * (n - len(a))) > (b + (0,) * (n - len(b)))


def _status_summary(db: Session) -> dict:
    """已购数 / 可更新数 / 最近到期，全部读进程内授权快照（不打网络、不查库以外的事）。

    快照由 sync_entitlements 写入：打开市场页时刷一次，另有门控线程每
    ENTITLEMENT_SYNC_MINUTES 分钟刷一次。所以这些数字是「最近一次同步时」的口径，
    页面同时返回 snapshot_synced_at 供前端标注新鲜度。
    """
    active = [
        e for e in (runtime.entitlements or {}).values()
        if isinstance(e, dict) and str(e.get("state") or "") == "active"
    ]
    updatable = 0
    for e in active:
        info = runtime.installed.get(str(e.get("app_key") or ""))
        if not info:
            continue
        installed_v = str(getattr(info.get("manifest"), "version", "") or "")
        if _is_newer(str(e.get("latest_version") or ""), installed_v):
            updatable += 1

    nearest_raw: str | None = None
    nearest_dt: datetime | None = None
    for e in active:
        raw = e.get("expires_at")
        if not raw:
            continue          # 一次性买断：expires_at 为空，不参与「最近到期」
        try:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if nearest_dt is None or dt < nearest_dt:
            nearest_dt, nearest_raw = dt, str(raw)

    return {
        "hub_reachable": _LAST_SYNC_OK,
        "purchased_count": len(active),
        "updatable_count": updatable,
        "nearest_expiry": nearest_raw,
        "snapshot_synced_at": runtime.synced_at or "",
    }


# ── 连接状态 / hub 配置 ──────────────────────────────────────────────────────

@router.get("/status")
def market_status(db: Session = Depends(get_db)):
    """连接状态：是否已配置 hub、是否已绑定门户账号，外加已购/可更新概况。

    概况字段是纯增量，老前端不读也不受影响。
    """
    hub = _hub_url(db)
    token = _get_instance_token(db)
    return ok({
        "hub_url": hub,
        "product": PRODUCT,
        "bound": bool(token),
        "account": _get_setting(db, ACCOUNT_KEY),
        "instance_uid": _get_setting(db, INSTANCE_UID_KEY),
        **_status_summary(db),
    })


@router.put("/hub")
def save_hub(payload: HubIn, db: Session = Depends(get_db)):
    """设置 hub 地址（如 https://admin.cenkor.cn）。"""
    _set_setting(db, HUB_URL_KEY, _normalize_hub_url(payload.hub_url))
    return ok({"message": "hub 地址已保存", "hub_url": _hub_url(db)})


# ── 设备码绑定向导 ───────────────────────────────────────────────────────────

@router.post("/bind/start")
def bind_start(request: Request, db: Session = Depends(get_db)):
    """向 hub 申请一次性绑定码，返回给用户去门户确认。"""
    url = _store_url(db, "public/cloud/device/start")
    body = {
        "instance_name": "CenkorMES 实例",
        "instance_url": _instance_url(request),
        "instance_uid": _instance_uid(db),
        "product": PRODUCT,
    }
    try:
        with httpx.Client(timeout=20) as client:
            resp = client.post(url, json=body)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"hub 不可达：{e}") from e
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"申请绑定码失败：{resp.status_code} {resp.text[:200]}")

    data = resp.json()
    _set_setting(db, BIND_DEVICE_CODE_KEY, data.get("device_code", ""))
    return ok({
        "user_code": data.get("user_code"),
        "verification_uri": data.get("verification_uri"),
        "verification_uri_complete": data.get("verification_uri_complete"),
        "expires_in": data.get("expires_in"),
        "interval": data.get("interval", 5),
    })


@router.get("/bind/poll")
def bind_poll(db: Session = Depends(get_db)):
    """轮询绑定结果；首次 approved 时换发并持久化 instance_token。"""
    device_code = _get_setting(db, BIND_DEVICE_CODE_KEY)
    if not device_code:
        return ok({"status": "idle"})
    url = _store_url(db, "public/cloud/device/poll")
    try:
        with httpx.Client(timeout=20) as client:
            resp = client.post(url, json={"device_code": device_code})
    except Exception as e:  # noqa: BLE001
        return ok({"status": "error", "message": f"hub 不可达：{e}"})
    if resp.status_code != 200:
        return ok({"status": "error", "message": f"{resp.status_code} {resp.text[:200]}"})

    data = resp.json()
    status = data.get("status")
    if status == "approved":
        _set_instance_token(db, data.get("instance_token", ""))
        if data.get("instance_uid"):
            _set_setting(db, INSTANCE_UID_KEY, data["instance_uid"])
        _set_setting(db, ACCOUNT_KEY, data.get("account") or "")
        _clear_setting(db, BIND_DEVICE_CODE_KEY)
        # 绑定成功后立即刷新一次授权快照，启动到期门控（失败开放）
        try:
            sync_entitlements(db)
        except Exception as e:  # noqa: BLE001
            logger.warning("market.bind_sync_after_approve_failed: %s", e)
        return ok({"status": "approved", "account": data.get("account")})
    # pending / expired / denied / consumed：expired/denied/consumed 清理临时码
    if status in ("expired", "denied", "consumed"):
        _clear_setting(db, BIND_DEVICE_CODE_KEY)
    return ok({"status": status})


@router.post("/bind/cancel")
def bind_cancel(db: Session = Depends(get_db)):
    """放弃当前未完成的绑定。"""
    _clear_setting(db, BIND_DEVICE_CODE_KEY)
    return ok({"message": "已取消绑定"})


@router.post("/bind/unbind")
def bind_unbind(db: Session = Depends(get_db)):
    """解绑本实例：通知 hub 吊销令牌并清理本地凭证。"""
    token = _get_instance_token(db)
    if token:
        try:
            url = _store_url(db, "cloud/instance/revoke-self")
            with httpx.Client(timeout=20) as client:
                client.post(url, headers=_bearer(token))
        except Exception as e:  # noqa: BLE001
            logger.warning("market.unbind_failed: %s", e)
    _clear_setting(db, INSTANCE_TOKEN_KEY)
    _clear_setting(db, ACCOUNT_KEY)
    _clear_setting(db, BIND_DEVICE_CODE_KEY)
    # 解绑后解除运行期门控，回到本地放行
    runtime.clear_entitlement_enforcement()
    return ok({"message": "已解绑"})


# ── hub 数据拉取 helpers ─────────────────────────────────────────────────────

def _fetch_catalog(db: Session) -> list[dict]:
    """可购目录（公开，按产品过滤）。失败返回空列表。"""
    try:
        url = _store_url(db, f"apps?product={PRODUCT}&page=1&page_size=100")
        with httpx.Client(timeout=15) as client:
            resp = client.get(url)
        if resp.status_code == 200:
            return resp.json().get("items", []) or []
    except Exception as e:  # noqa: BLE001
        logger.warning("market.fetch_catalog_failed: %s", e)
    return []


def _fetch_purchases(db: Session) -> list[dict]:
    """已购授权（需 Bearer 实例令牌）。未绑定/失败返回空列表。"""
    token = _get_instance_token(db)
    if not token:
        return []
    try:
        url = _store_url(db, "cloud/my-purchases")
        with httpx.Client(timeout=15) as client:
            resp = client.get(url, headers=_bearer(token))
        if resp.status_code == 200:
            return resp.json().get("items", []) or []
        logger.warning("market.fetch_purchases_status: %s", resp.status_code)
    except Exception as e:  # noqa: BLE001
        logger.warning("market.fetch_purchases_failed: %s", e)
    return []


def _fetch_purchases_checked(db: Session) -> tuple[bool, list[dict]]:
    """拉取已购并区分成否：返回 (是否 HTTP 200, 条目)。

    未绑定（无 token）或请求异常/非 200 均返回 (False, [])，供上层失败开放。
    """
    token = _get_instance_token(db)
    if not token:
        return False, []
    try:
        url = _store_url(db, "cloud/my-purchases")
        with httpx.Client(timeout=15) as client:
            resp = client.get(url, headers=_bearer(token))
        if resp.status_code == 200:
            return True, resp.json().get("items", []) or []
        logger.warning("market.purchases_http_%s", resp.status_code)
        return False, []
    except Exception as e:  # noqa: BLE001
        logger.warning("market.purchases_check_failed: %s", e)
        return False, []


def _purchase_state(p: dict) -> str:
    """将 hub 已购条目归类为运行期授权态：active / expired / revoked / suspended。"""
    status = str(p.get("status") or "").lower()
    if status in ("revoked", "suspended"):
        return status
    exp = p.get("expires_at")
    if exp:
        try:
            dt = datetime.fromisoformat(str(exp).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt < datetime.now(timezone.utc):
                return "expired"
        except (ValueError, TypeError):
            pass
    # issued（已付未激活）/ active 均视为已授权
    return "active"


def sync_entitlements(db: Session) -> bool:
    """用 hub 已购快照刷新运行期门控（失败开放）。

    返回是否成功拉到快照并置位门控。未绑定→解除门控；hub 不可达/非 200 →
    保留上一次快照不变（不误停用）。
    顺带把结果记进 `_LAST_SYNC_OK`，供 `/status` 回答「hub 可不可达」。
    """
    global _LAST_SYNC_OK
    token = _get_instance_token(db)
    if not token:
        _LAST_SYNC_OK = None          # 未绑定：不谈可达性
        runtime.clear_entitlement_enforcement()
        return False
    success, purchases = _fetch_purchases_checked(db)
    _LAST_SYNC_OK = success
    if not success:
        return False
    snapshot: dict[str, dict] = {}
    for p in purchases:
        key = p.get("app_key")
        if not key:
            continue
        snapshot[key] = {
            "app_key": key,
            "state": _purchase_state(p),
            "latest_version": p.get("latest_version") or "",
            "expires_at": p.get("expires_at"),
            "license_key": p.get("license_key"),
        }
    synced_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    runtime.set_entitlement_snapshot(snapshot, synced_at, enforced=True)
    logger.info("[market] 授权快照已刷新（%d 项，已启用到期门控）", len(snapshot))
    return True


def _entitlement_sync_once() -> None:
    db = SessionLocal()
    try:
        sync_entitlements(db)
    except Exception as e:  # noqa: BLE001
        logger.warning("market.entitlement_sync_error: %s", e)
    finally:
        db.close()


def _entitlement_loop(stop_event: "threading.Event") -> None:
    _entitlement_sync_once()
    while not stop_event.wait(ENTITLEMENT_SYNC_MINUTES * 60):
        _entitlement_sync_once()


def start_entitlement_thread() -> None:
    """启动 web 进程内的授权到期门控线程（daemon，失败开放）。幂等。"""
    if ENTITLEMENT_SYNC_MINUTES <= 0:
        return
    if runtime.sync_thread and runtime.sync_thread.is_alive():
        return
    stop_event = threading.Event()
    t = threading.Thread(
        target=_entitlement_loop, args=(stop_event,),
        name="market-entitlement-sync", daemon=True,
    )
    t.start()
    runtime.sync_thread = t
    logger.info("[market] 授权到期门控线程已启动（每 %d 分钟）", ENTITLEMENT_SYNC_MINUTES)


def _license_for(purchases: list[dict], app_key: str) -> dict | None:
    """从已购里找该 app 当前可用的授权（未过期、未吊销）。"""
    best = None
    for p in purchases:
        if p.get("app_key") != app_key:
            continue
        status = p.get("status")
        if status in ("revoked", "suspended", "expired"):
            continue
        if best is None or (p.get("license_key") or "") > (best.get("license_key") or ""):
            best = p
    return best


# ── 应用目录（合并 hub 目录 + 已购 + 本地已装）────────────────────────────────

@router.get("/apps")
def list_market_apps(db: Session = Depends(get_db)):
    """功能市场列表：hub 目录 + 已购授权 + 本地已装状态合并。"""
    # 先刷新授权快照（失败开放），使“到期/吊销自动停用”与目录展示保持一致
    try:
        sync_entitlements(db)
    except Exception as e:  # noqa: BLE001
        logger.warning("market.apps_sync_entitlements_failed: %s", e)
    token = _get_instance_token(db)
    catalog = _fetch_catalog(db)
    purchases = _fetch_purchases(db)
    licensed = {p.get("app_key"): p for p in purchases if p.get("app_key")}

    items: list[dict] = []
    seen: set[str] = set()
    for app in catalog:
        key = app.get("app_key") or app.get("key") or ""
        if not key or key in seen:
            continue
        seen.add(key)
        lic = licensed.get(key)
        info = runtime.installed.get(key)
        manifest = info.get("manifest") if info else None
        items.append({
            "key": key,
            "name": app.get("name", ""),
            "description": app.get("description", "") or app.get("summary", ""),
            "icon": app.get("icon", ""),
            "category": app.get("category", ""),
            # hub 若已下发 latest_version（同轴上架行里版本号最大的一条）就以它为准；
            # 老 hub 只有 version 时等价退回。绝不拿字符串不等当「有更新」。
            "latest_version": app.get("latest_version") or app.get("version", ""),
            # 更新弹窗展示用：hub 目录已带 changelog / min_core_version / schema_version，
            # 老 hub 缺字段时留空，前端按「未声明」降级展示。
            "changelog": app.get("changelog") or "",
            "min_core_version": app.get("min_core_version") or "",
            "schema_version": app.get("schema_version"),
            "price": app.get("price"),
            "licensed": lic is not None,
            "license_state": (lic or {}).get("status", ""),
            "license_expires_at": (lic or {}).get("expires_at"),
            "bound_instances": (lic or {}).get("bound_instances", 0),
            "max_instances": (lic or {}).get("max_instances", 1),
            "installed": info is not None,
            "installed_version": getattr(manifest, "version", "") if manifest else "",
            "enabled": runtime.is_enabled(key) if info else False,
        })

    # 已购但不在公开目录里的（例如定向发放）也补进来，保证能装
    for key, lic in licensed.items():
        if key in seen:
            continue
        seen.add(key)
        info = runtime.installed.get(key)
        manifest = info.get("manifest") if info else None
        items.append({
            "key": key,
            "name": lic.get("app_name", key),
            "description": "",
            "icon": "",
            "category": "",
            # 不在目录里也要能提示更新：hub 的已购接口自带最新可分发版本，缺值就安静
            "latest_version": lic.get("latest_version") or "",
            "changelog": lic.get("changelog") or "",
            "min_core_version": lic.get("min_core_version") or "",
            "schema_version": lic.get("schema_version"),
            "price": lic.get("price"),
            "licensed": True,
            "license_state": lic.get("status", ""),
            "license_expires_at": lic.get("expires_at"),
            "bound_instances": lic.get("bound_instances", 0),
            "max_instances": lic.get("max_instances", 1),
            "installed": info is not None,
            "installed_version": getattr(manifest, "version", "") if manifest else "",
            "enabled": runtime.is_enabled(key) if info else False,
        })

    # 本地已装、但既不在目录也不在已购里的（样例/定向安装/hub 未上架）：
    # 仍列入以便在本页启用/禁用/卸载（修复“装了却在市场看不到”的可见性问题）。
    for key, info in runtime.installed.items():
        if key in seen:
            continue
        seen.add(key)
        manifest = info.get("manifest")
        lic = licensed.get(key)
        installed_version = getattr(manifest, "version", "") or ""
        items.append({
            "key": key,
            "name": getattr(manifest, "name", "") or key,
            "description": getattr(manifest, "description", "") or "",
            "icon": getattr(manifest, "icon", "") or "",
            "category": getattr(manifest, "category", "") or "",
            "latest_version": installed_version,
            "changelog": "",
            "min_core_version": getattr(manifest, "min_core_version", "") or "",
            "schema_version": getattr(manifest, "schema_version", None),
            "price": (lic or {}).get("price"),
            "licensed": lic is not None,
            "license_state": (lic or {}).get("status", ""),
            "license_expires_at": (lic or {}).get("expires_at"),
            "bound_instances": (lic or {}).get("bound_instances", 0),
            "max_instances": (lic or {}).get("max_instances", 1),
            "installed": True,
            "installed_version": installed_version,
            "enabled": runtime.is_enabled(key),
        })

    # 生命周期登记字段（health/status/worker_restart_required…）合并进目录项，
    # 前端卡片据此展示「已装版本 / 最新版本 / 健康 / 上次操作 / 需重启 worker」。
    from app.extension_host.registry import registry_info

    for item in items:
        record = registry_info(item["key"]) or {}
        item.setdefault("health", record.get("health") or "")
        item["status"] = record.get("status") or ""
        item["previous_version"] = record.get("previous_version") or ""
        item["last_operation"] = record.get("last_operation") or ""
        item["last_error"] = record.get("last_error") or ""
        item["data_policy"] = record.get("data_policy") or "keep"
        item["worker_restart_required"] = bool(record.get("worker_restart_required"))
        item["multi_worker"] = bool(record.get("multi_worker"))
        item["has_backup"] = bool(record.get("backup"))

    return ok({
        "items": items,
        "hub_url": _hub_url(db),
        "bound": bool(token),
        "account": _get_setting(db, ACCOUNT_KEY),
    })


# ── 安装 / 卸载（复用热加载引擎）─────────────────────────────────────────────

def _activate_license(db: Session, license_key: str, request: Request) -> None:
    """把授权绑定到本实例（席位/域名记账）。best-effort：失败不阻断下载。"""
    try:
        url = _store_url(db, f"licenses/{license_key}/activate")
        body = {
            "instance_fp": _instance_uid(db),
            "domain": _instance_url(request),
            "version": getattr(runtime, "app_version", "") or "",
        }
        with httpx.Client(timeout=30) as client:
            resp = client.post(url, json=body)
        if resp.status_code not in (200, 409):
            logger.warning("market.activate_status: %s %s", resp.status_code, resp.text[:200])
    except Exception as e:  # noqa: BLE001
        logger.warning("market.activate_failed: %s", e)


def _download_package(db: Session, app_key: str, license_key: str) -> tuple[bytes, str]:
    """拉包，并带回 hub 权威的产品轴（X-App-Product，老 hub 无此头则空串）。

    返回头而非改写包内 manifest：包是开发者自述，头是 hub 按 license.product 发的。
    经 hub/spoke 中转的下发路径不透传响应头，此时退化为空串，由 manifest 那道闸兜底。
    """
    url = _store_url(db, f"cloud/packages/{app_key}")
    with httpx.Client(timeout=120, follow_redirects=True) as client:
        resp = client.get(url, params={"license_key": license_key})
    if resp.status_code == 403:
        raise HTTPException(status_code=403, detail="未授权或授权已失效，请先在门户购买/领取该扩展")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"hub 返回错误：{resp.status_code} {resp.text[:200]}")
    # 包体指纹校验：hub 随包下发**发布当时**算好的 SHA256。缺值即放行（老 hub 无此头，
    # 或经 spoke 中转被剥掉），有值而不等就是拿到的字节与目录里那条发布记录不是同一份。
    content = resp.content
    expected = (resp.headers.get("X-Package-Sha256") or "").strip().lower()
    if expected:
        actual = hashlib.sha256(content).hexdigest()
        if actual != expected:
            logger.error(
                "market.package_sha256_mismatch app=%s expected=%s actual=%s size=%s",
                app_key, expected, actual, len(content),
            )
            raise HTTPException(
                status_code=502,
                detail=(
                    f"扩展包校验失败：SHA256 与 hub 发布记录不一致"
                    f"（期望 {expected[:12]}…，实得 {actual[:12]}…），已拒绝安装"
                ),
            )
    return content, (resp.headers.get("X-App-Product") or "").strip()


def _install_extension(package_bytes: bytes, app_key: str) -> dict:
    """校验并落盘扩展包（staging → 备份 → 换入），不负责迁移与挂载。

    product 护栏、key 正则、zip 成员白名单、semver、核心版本、依赖与表冲突都在
    ``preflight`` 里完成；任何一步失败都不会碰已装目录（不存在先删后解压）。
    """
    base = extensions_base_dir()
    with use_base(base):
        try:
            pre = preflight(package_bytes, app_key, product=PRODUCT)
            stage_dir = stage(package_bytes, pre)
            live = base / pre.key
            backup = backup_target(pre.key, "(previous)") if live.exists() else None
            moved = swap(pre.key, stage_dir, backup)
        except LifecycleError as e:
            raise HTTPException(status_code=e.status_code, detail=str(e)) from e
        except Exception as e:  # noqa: BLE001 - 解压/落盘异常统一 400
            raise HTTPException(status_code=400, detail=f"扩展包安装失败：{e}") from e
    return {
        "key": pre.key,
        "version": pre.version,
        "path": str(base / pre.key),
        "sha256": pre.sha256,
        "backup": moved.get("backup", ""),
    }


def _actor(user) -> str:
    name = getattr(user, "username", "") or getattr(user, "full_name", "") or ""
    return str(name)


def _lifecycle_error(e: LifecycleError) -> HTTPException:
    return HTTPException(status_code=e.status_code, detail={"message": str(e), **e.extra})


def _refresh_purchases(db: Session) -> None:
    """安装完成后异步刷新已购快照（授权字段/最新版本号）。"""
    try:
        purchases = _fetch_purchases(db)
        if purchases:
            logger.info("market.purchases_refreshed count=%s", len(purchases))
    except Exception as e:  # noqa: BLE001 - 刷新失败不影响安装结果
        logger.warning("market.purchases_refresh_failed: %s", e)


@router.post("/install", dependencies=_LIFECYCLE_MGMT)
def install_app(
    payload: InstallIn,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """从 hub 下载并安装/更新扩展（staging → 迁移 → 换入 → 挂载 → 健康检查）。"""
    purchases = _fetch_purchases(db)
    lic = _license_for(purchases, payload.app_key)
    if not lic or not lic.get("license_key"):
        raise HTTPException(status_code=403, detail="尚未持有该扩展的有效授权，请先在 Cenkor 门户购买/领取")

    license_key = lic["license_key"]
    # 可信版产品轴：license.product 来自 hub 库里的签发记录（老 hub 不返回该字段则跳过），
    # 比包内自述的 manifest.product 更可信——前者是平台写的，后者是开发者写的。
    lic_product = lic.get("product")
    if lic_product and lic_product != PRODUCT:
        raise HTTPException(
            status_code=400,
            detail=f"该授权属于产品「{lic_product}」，与本实例「{PRODUCT}」不符",
        )
    _activate_license(db, license_key, request)
    package_bytes, hub_product = _download_package(db, payload.app_key, license_key)
    # hub 随包下发的权威产品轴：对不写 manifest.product 的包同样生效
    if hub_product and hub_product != PRODUCT:
        raise HTTPException(
            status_code=400,
            detail=f"该应用包属于产品「{hub_product}」，与本实例「{PRODUCT}」不符",
        )

    try:
        result = install_or_update(
            request.app,
            package_bytes,
            payload.app_key,
            actor=_actor(user),
            allow_downgrade=payload.allow_downgrade,
            product=PRODUCT,
        )
    except LifecycleError as e:
        raise _lifecycle_error(e) from e
    _refresh_purchases(db)
    return ok({
        "message": "安装成功，已即时生效" if result["action"] == "install" else "更新成功，已即时生效",
        **result,
        "hot_loaded": runtime.is_enabled(result["key"]),
    })


@router.post("/apps/{key}/install", dependencies=_LIFECYCLE_MGMT)
def install_app_by_key(
    key: str,
    request: Request,
    payload: InstallIn | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """RESTful 别名：安装/更新指定 key（body 可省略，默认不允许降级）。"""
    return install_app(
        payload or InstallIn(app_key=key), request, db=db, user=user
    )


@router.post("/uninstall", dependencies=_LIFECYCLE_MGMT)
def uninstall_app(
    payload: UninstallIn,
    request: Request,
    user=Depends(get_current_user),
):
    """卸载扩展：默认保留数据（keep），``purge=true`` 走彻底清除（需 confirm_key）。"""
    try:
        result = uninstall(
            request.app,
            payload.app_key,
            purge=payload.purge,
            confirm_key=payload.confirm_key or None,
            actor=_actor(user),
        )
    except LifecycleError as e:
        raise _lifecycle_error(e) from e
    return ok(result)


@router.post("/apps/{key}/uninstall", dependencies=_LIFECYCLE_MGMT)
def uninstall_app_by_key(
    key: str,
    request: Request,
    payload: UninstallIn | None = None,
    user=Depends(get_current_user),
):
    body = payload or UninstallIn(app_key=key)
    return uninstall_app(body, request, user=user)


@router.post("/apps/{key}/enable", dependencies=_LIFECYCLE_MGMT)
def enable_app(key: str, request: Request, user=Depends(get_current_user)):
    """软插：清 override，跑迁移/补权限，重新挂载路由与事件。"""
    try:
        result = set_enabled(request.app, key, True, actor=_actor(user))
    except LifecycleError as e:
        raise _lifecycle_error(e) from e
    return ok({"message": "已启用", **result})


@router.post("/apps/{key}/disable", dependencies=_LIFECYCLE_MGMT)
def disable_app(key: str, request: Request, user=Depends(get_current_user)):
    """软拔：停门禁、摘路由/事件/任务，保留文件与数据。"""
    try:
        result = set_enabled(request.app, key, False, actor=_actor(user))
    except LifecycleError as e:
        raise _lifecycle_error(e) from e
    return ok({"message": "已禁用（文件与数据保留）", **result})


@router.post("/apps/{key}/rollback", dependencies=_LIFECYCLE_MGMT)
def rollback_app(key: str, request: Request, user=Depends(get_current_user)):
    """回滚到最近备份版本；旧版不兼容新 schema 时保持新版并标记 rollback_blocked。"""
    try:
        result = rollback(request.app, key, actor=_actor(user))
    except LifecycleError as e:
        raise _lifecycle_error(e) from e
    return ok({"message": "已回滚", **result})


@router.post("/apps/{key}/repair", dependencies=_LIFECYCLE_MGMT)
def repair_app(key: str, request: Request, user=Depends(get_current_user)):
    """修复：目录丢失从备份还原，补迁移/补权限，重新挂载并健康检查。"""
    try:
        result = repair(request.app, key, actor=_actor(user))
    except LifecycleError as e:
        raise _lifecycle_error(e) from e
    return ok({"message": "修复完成", **result})


@router.get("/lifecycle/logs", dependencies=_LIFECYCLE_MGMT)
def get_lifecycle_logs(
    limit: int = 100,
    key: str | None = None,
):
    """生命周期审计（谁、何时、从哪个版本到哪个版本、结果、耗时、包 SHA）。"""
    limit = max(1, min(int(limit or 100), 500))
    return ok({"items": lifecycle_logs(limit=limit, key=key)})
