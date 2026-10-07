# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""扩展宿主运行时状态：内存态 + 落盘缓存。

MES 侧不新增数据库表，全部状态落在 ``extensions/.state/``：

- ``entitlements.json``  应用中心下发的授权快照（离线时沿用上次结果）
- ``overrides.json``     本地启停覆盖（CLI 维护，disabled 优先于一切）
- ``migrations.json``    已执行的扩展迁移指纹（幂等控制）
"""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger("uvicorn.error")


class StateStore:
    """``.state`` 目录下的 JSON 文件读写（原子写 + 线程安全）。"""

    def __init__(self, state_dir: Path):
        self._dir = state_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, name: str) -> Path:
        return self._dir / f"{name}.json"

    def load(self, name: str, default: Any) -> Any:
        path = self._path(name)
        if not path.is_file():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("[extension] 读取 %s 失败: %s", path, e)
            return default

    def save(self, name: str, data: Any) -> None:
        path = self._path(name)
        tmp = path.with_suffix(".tmp")
        with self._lock:
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(path)


class ExtensionRuntime:
    """宿主运行时状态（进程内单例）。"""

    def __init__(self) -> None:
        self.extensions_dir: Path | None = None
        self.store: StateStore | None = None
        self.installed: dict[str, dict] = {}      # key -> {"manifest": ..., "path": Path}
        self.entitlements: dict[str, dict] = {}   # app_key -> 授权快照条目
        self.entitlement_enforced: bool = False    # 是否已根据 hub 已购快照启用运行期门控
        self.overrides: dict[str, str] = {}       # key -> "disabled"
        self.synced_at: str = ""
        self.sync_thread: threading.Thread | None = None

    # ---------- 启用判定 ----------
    def entitlement_state(self, key: str) -> str:
        """授权状态。

        失败开放（fail-open）：未绑定 hub、或自启动以来未成功拉到一次已购快照时，
        一律返回 ``local``（装了即启用），以免 hub 不可达时误停用正在运行的扩展。
        仅在绑定且最近一次同步成功后（``entitlement_enforced``）才按快照判定：
        命中 active 放行；expired/revoked 或未命中则停用。
        """
        if not self.entitlement_enforced:
            return "local"
        ent = self.entitlements.get(key)
        if not ent:
            return "none"
        return str(ent.get("state") or "none")

    def is_enabled(self, key: str) -> bool:
        """启用判定：已安装 且 未被本地禁用 且（本地放行 或 授权 active）。"""
        if key not in self.installed:
            return False
        if self.overrides.get(key) == "disabled":
            return False
        return self.entitlement_state(key) in ("local", "active")

    # ---------- 状态快照 ----------
    def status_list(self) -> list[dict]:
        """全部已安装扩展的状态（供宿主 API / CLI）。"""
        items: list[dict] = []
        for key, info in sorted(self.installed.items()):
            manifest = info["manifest"]
            ent = self.entitlements.get(key) or {}
            latest = str(ent.get("latest_version") or "")
            items.append({
                **manifest.to_dict(),
                "enabled": self.is_enabled(key),
                "entitlement": self.entitlement_state(key),
                "latest_version": latest,
                "upgrade_available": bool(latest and latest != manifest.version),
                "has_frontend": (Path(info["path"]) / "frontend" / "plugin.js").is_file(),
            })
        return items

    # ---------- 缓存读写 ----------
    def load_from_disk(self) -> None:
        """从 .state 恢复缓存（授权快照 / 本地覆盖）。"""
        if not self.store:
            return
        cached = self.store.load("entitlements", {}) or {}
        self.synced_at = str(cached.get("synced_at") or "")
        self.entitlements = {
            x["app_key"]: x
            for x in (cached.get("entitlements") or [])
            if isinstance(x, dict) and x.get("app_key")
        }
        self.overrides = {str(k): str(v) for k, v in (self.store.load("overrides", {}) or {}).items()}

    def apply_entitlements(self, body: dict, synced_at: str) -> None:
        """授权快照 → 更新内存 + 落盘（兼容旧调用方）。"""
        raw_items = [
            x for x in (body.get("entitlements") or [])
            if isinstance(x, dict) and x.get("app_key")
        ]
        self.entitlements = {x["app_key"]: x for x in raw_items}
        self.synced_at = synced_at
        if self.store:
            self.store.save("entitlements", {"synced_at": synced_at, "entitlements": raw_items})

    def set_entitlement_snapshot(self, items: dict[str, dict], synced_at: str, *, enforced: bool = True) -> None:
        """用 hub 已购快照刷新运行期门控状态。

        items: app_key -> {"state": "active"/"expired"/"revoked", ...}。
        enforced: 是否启用运行期门控（失败开放下，只有成功同步才置 True）。
        """
        self.entitlements = items
        self.entitlement_enforced = enforced
        self.synced_at = synced_at
        if self.store:
            self.store.save(
                "entitlements",
                {"synced_at": synced_at, "entitlements": list(items.values()), "enforced": enforced},
            )

    def clear_entitlement_enforcement(self) -> None:
        """解除运行期门控（未绑定 / 解绑）：回到本地放行。"""
        self.entitlement_enforced = False
        self.entitlements = {}
        if self.store:
            self.store.save("entitlements", {"synced_at": "", "entitlements": [], "enforced": False})

    def set_override(self, key: str, value: str | None) -> None:
        """设置/清除本地启停覆盖（value: "disabled" 或 None）。"""
        if value:
            self.overrides[key] = value
        else:
            self.overrides.pop(key, None)
        if self.store:
            self.store.save("overrides", self.overrides)

    def reset(self) -> None:
        """重置运行时状态（测试/CLI 使用）。"""
        self.extensions_dir = None
        self.store = None
        self.installed = {}
        self.entitlements = {}
        self.entitlement_enforced = False
        self.overrides = {}
        self.synced_at = ""
        self.sync_thread = None


runtime = ExtensionRuntime()
