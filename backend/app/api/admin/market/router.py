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

import json
import logging
import shutil
import threading
import uuid
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.deps import get_db
from app.core.response import ok
from app.extension_host.host import (
    extensions_base_dir,
    hot_setup_extension,
    hot_teardown_extension,
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
    app_key: str = Field(min_length=1, max_length=64)


class UninstallIn(BaseModel):
    app_key: str = Field(min_length=1, max_length=64)


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


def _hub_url(db: Session) -> str:
    return _get_setting(db, HUB_URL_KEY).rstrip("/")


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


# ── 连接状态 / hub 配置 ──────────────────────────────────────────────────────

@router.get("/status")
def market_status(db: Session = Depends(get_db)):
    """连接状态：是否已配置 hub、是否已绑定门户账号。"""
    hub = _hub_url(db)
    token = _get_setting(db, INSTANCE_TOKEN_KEY)
    return ok({
        "hub_url": hub,
        "product": PRODUCT,
        "bound": bool(token),
        "account": _get_setting(db, ACCOUNT_KEY),
        "instance_uid": _get_setting(db, INSTANCE_UID_KEY),
    })


@router.put("/hub")
def save_hub(payload: HubIn, db: Session = Depends(get_db)):
    """设置 hub 地址（如 https://admin.cenkor.cn）。"""
    _set_setting(db, HUB_URL_KEY, payload.hub_url.strip().rstrip("/"))
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
        _set_setting(db, INSTANCE_TOKEN_KEY, data.get("instance_token", ""))
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
    token = _get_setting(db, INSTANCE_TOKEN_KEY)
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
    token = _get_setting(db, INSTANCE_TOKEN_KEY)
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
    token = _get_setting(db, INSTANCE_TOKEN_KEY)
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
    """
    token = _get_setting(db, INSTANCE_TOKEN_KEY)
    if not token:
        runtime.clear_entitlement_enforcement()
        return False
    success, purchases = _fetch_purchases_checked(db)
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
    token = _get_setting(db, INSTANCE_TOKEN_KEY)
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
            "latest_version": app.get("version", ""),
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
            "latest_version": "",
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


def _download_package(db: Session, app_key: str, license_key: str) -> bytes:
    url = _store_url(db, f"cloud/packages/{app_key}")
    with httpx.Client(timeout=120, follow_redirects=True) as client:
        resp = client.get(url, params={"license_key": license_key})
    if resp.status_code == 403:
        raise HTTPException(status_code=403, detail="未授权或授权已失效，请先在门户购买/领取该扩展")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"hub 返回错误：{resp.status_code} {resp.text[:200]}")
    return resp.content


def _install_extension(package_bytes: bytes, app_key: str) -> dict:
    """解压并安装扩展包到 extensions/ 目录。"""
    extensions_dir = extensions_base_dir()
    extensions_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(BytesIO(package_bytes)) as zf:
        manifest_data = None
        for name in zf.namelist():
            if name.endswith("/manifest.json") or name == "manifest.json":
                manifest_data = json.loads(zf.read(name))
                break
        if not manifest_data:
            raise HTTPException(status_code=400, detail="扩展包缺少 manifest.json")

        pkg_key = manifest_data.get("key", "")
        pkg_version = manifest_data.get("version", "")
        if pkg_key != app_key:
            raise HTTPException(status_code=400, detail=f"扩展 key 不匹配：{pkg_key} != {app_key}")

        target_dir = extensions_dir / pkg_key
        if target_dir.exists():
            shutil.rmtree(target_dir)
        for member in zf.namelist():
            if "__MACOSX" in member or member.startswith("."):
                continue
            zf.extract(member, str(target_dir))
        for f in target_dir.rglob("*"):
            if f.is_file():
                f.chmod(0o644)
            elif f.is_dir():
                f.chmod(0o755)

        return {"key": pkg_key, "version": pkg_version, "path": str(target_dir)}


@router.post("/install")
def install_app(payload: InstallIn, request: Request, db: Session = Depends(get_db)):
    """从 hub 下载并安装扩展（需已购授权；热生效，无需重启）。"""
    purchases = _fetch_purchases(db)
    lic = _license_for(purchases, payload.app_key)
    if not lic or not lic.get("license_key"):
        raise HTTPException(status_code=403, detail="尚未持有该扩展的有效授权，请先在 Cenkor 门户购买/领取")

    license_key = lic["license_key"]
    _activate_license(db, license_key, request)
    package_bytes = _download_package(db, payload.app_key, license_key)
    result = _install_extension(package_bytes, payload.app_key)

    # 刷新运行时状态 + 运行期热挂载（迁移/权限/路由，无需重启）
    scan_dir = runtime.extensions_dir or extensions_base_dir()
    runtime.installed = scan_extensions(scan_dir)
    hot_setup_extension(request.app, result["key"])

    return ok({
        "message": "安装成功，已即时生效",
        "key": result["key"],
        "version": result["version"],
        "path": result["path"],
        "hot_loaded": runtime.is_enabled(result["key"]),
    })


@router.post("/uninstall")
def uninstall_app(payload: UninstallIn, request: Request):
    """卸载已安装的扩展（删除 extensions/{key}/ 目录，热生效）。"""
    app_key = payload.app_key
    info = runtime.installed.get(app_key)
    if not info:
        raise HTTPException(status_code=404, detail="该扩展未安装")

    ext_path = Path(info["path"])
    base = extensions_base_dir().resolve()
    target = ext_path.resolve()
    if base not in target.parents and target != base / app_key:
        raise HTTPException(status_code=400, detail="非法的扩展路径，拒绝删除")

    try:
        shutil.rmtree(target)
    except FileNotFoundError:
        pass
    except Exception as e:  # noqa: BLE001
        logger.error("market.uninstall_remove_error: %s", e)
        raise HTTPException(status_code=500, detail=f"删除失败：{e}")

    scan_dir = runtime.extensions_dir or extensions_base_dir()
    runtime.installed = scan_extensions(scan_dir)
    hot_teardown_extension(request.app, app_key)

    return ok({"message": "卸载成功，已即时生效", "key": app_key})
