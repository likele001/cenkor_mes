# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""扩展声明文件（manifest.json）的读取与校验。

manifest v1 结构::

    {
      "key": "quotation_demo",           # 必填，须与扩展目录名一致
      "name": "报价单（演示）",           # 必填
      "version": "1.0.0",                # 必填
      "description": "",                  # 可选
      "icon": "Document",                 # 可选，Element Plus 图标名
      "category": "sales",                # 可选
      "vendor": "",                       # 可选
      "permissions": [                    # 可选，启用时注入权限点并补授 admin
        {"code": "ext.quotation.view", "name": "查看报价"}
      ],
      "menus": [                          # 可选，前端加载器动态注入菜单
        {"title": "报价单", "path": "/ext/quotation", "icon": "Document", "permission": "ext.quotation.view"}
      ]
    }
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .version import is_semver

_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
_ALLOWED_TABLE_MODES = {"own", "read", "write"}


class ManifestError(ValueError):
    """manifest 不合法。"""


@dataclass
class ExtensionManifest:
    """扩展清单。

    ``manifest_version=1`` 是存量格式，只做最小校验；``manifest_version=2``
    才启用权限命名空间、菜单路径、数据归属、依赖等强校验。
    """

    key: str
    name: str
    version: str
    description: str = ""
    icon: str = ""
    category: str = ""
    vendor: str = ""
    permissions: list[dict] = field(default_factory=list)
    menus: list[dict] = field(default_factory=list)
    manifest_version: int = 1
    schema_version: int = 0
    min_core_version: str = ""
    max_core_version: str = ""
    product: str = ""
    dev_method: str = ""
    data: dict = field(default_factory=dict)
    tasks: dict = field(default_factory=dict)
    dependencies: list[dict] = field(default_factory=list)
    changelog: str = ""

    @property
    def is_v2(self) -> bool:
        return self.manifest_version >= 2

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "icon": self.icon,
            "category": self.category,
            "vendor": self.vendor,
            "permissions": self.permissions,
            "menus": self.menus,
            "manifest_version": self.manifest_version,
            "schema_version": self.schema_version,
            "min_core_version": self.min_core_version,
            "max_core_version": self.max_core_version,
            "product": self.product,
            "dev_method": self.dev_method,
            "data": self.data,
            "tasks": self.tasks,
            "dependencies": self.dependencies,
            "changelog": self.changelog,
        }


def load_manifest(ext_dir: Path, check_dir_name: bool = True) -> ExtensionManifest:
    """读取并校验扩展目录下的 manifest.json。

    check_dir_name=False 用于安装场景（此时 manifest 尚未落入以 key 命名的目录）。
    """
    file = ext_dir / "manifest.json"
    if not file.is_file():
        raise ManifestError(f"缺少 manifest.json: {file}")
    try:
        raw = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ManifestError(f"manifest.json 读取失败: {e}")
    if not isinstance(raw, dict):
        raise ManifestError("manifest.json 必须是 JSON 对象")
    # name 兼容缺省（老包/测试包可能只写 key）：缺省回落 key 本身
    for name in ("key", "version"):
        value = raw.get(name)
        if not value or not isinstance(value, str):
            raise ManifestError(f"manifest.json 缺少必填字段 {name}")
    if check_dir_name and ext_dir.name != raw["key"]:
        raise ManifestError(f"manifest key（{raw['key']}）与目录名（{ext_dir.name}）不一致")

    manifest_version = int(raw.get("manifest_version") or (2 if raw.get("schema_version") else 1))
    if manifest_version not in (1, 2):
        raise ManifestError("manifest_version 只支持 1 或 2")
    if not _KEY_RE.match(raw["key"]):
        raise ManifestError(f"manifest key 不合法：{raw['key']!r}（要求 ^[a-z][a-z0-9_]{{1,63}}$）")
    if manifest_version >= 2 and not is_semver(raw["version"]):
        raise ManifestError(f"manifest.version 必须是 semver：{raw['version']!r}")

    permissions = raw.get("permissions") or []
    if not isinstance(permissions, list):
        raise ManifestError("permissions 必须是数组")
    menus = raw.get("menus") or []
    if not isinstance(menus, list):
        raise ManifestError("menus 必须是数组")

    cleaned_permissions: list[dict] = []
    for p in permissions:
        if not isinstance(p, dict) or not p.get("code"):
            continue
        code = str(p["code"]).strip()
        if manifest_version >= 2 and not code.startswith(f"ext.{raw['key']}."):
            raise ManifestError(f"权限码 {code!r} 必须落在 ext.{raw['key']}. 命名空间")
        cleaned_permissions.append({**p, "code": code})

    cleaned_menus: list[dict] = []
    for m in menus:
        if not isinstance(m, dict) or not m.get("path"):
            continue
        path = str(m["path"]).strip()
        if manifest_version >= 2 and not path.startswith("/ext/"):
            raise ManifestError(f"菜单路径 {path!r} 必须以 /ext/ 开头")
        cleaned_menus.append({**m, "path": path})

    data = raw.get("data") or {}
    if not isinstance(data, dict):
        raise ManifestError("data 必须是对象")
    retention = str(data.get("retention") or "keep")
    if retention not in ("keep", "ask"):
        raise ManifestError("data.retention 只允许 keep 或 ask")
    tables = data.get("tables") or []
    if not isinstance(tables, list):
        raise ManifestError("data.tables 必须是数组")
    for t in tables:
        if not isinstance(t, dict) or not t.get("name"):
            raise ManifestError("data.tables 每项必须包含 name")
        if str(t.get("mode") or "own") not in _ALLOWED_TABLE_MODES:
            raise ManifestError(f"data.tables[{t.get('name')}].mode 非法")

    tasks = raw.get("tasks") or {}
    if not isinstance(tasks, dict):
        raise ManifestError("tasks 必须是对象")
    for field_name in ("celery", "beat"):
        value = tasks.get(field_name) or []
        if not isinstance(value, list):
            raise ManifestError(f"tasks.{field_name} 必须是数组")

    dependencies = raw.get("dependencies") or []
    if not isinstance(dependencies, list):
        raise ManifestError("dependencies 必须是数组")
    for dep in dependencies:
        if not isinstance(dep, dict) or not dep.get("key"):
            raise ManifestError("dependencies 每项必须包含 key")

    min_core = str(raw.get("min_core_version") or "")
    if min_core and not is_semver(min_core):
        raise ManifestError(f"min_core_version 必须是 semver：{min_core!r}")
    max_core = str(raw.get("max_core_version") or "")
    if max_core and not is_semver(max_core):
        raise ManifestError(f"max_core_version 必须是 semver：{max_core!r}")

    return ExtensionManifest(
        key=raw["key"],
        name=str(raw.get("name") or raw["key"]),
        version=raw["version"],
        description=str(raw.get("description") or ""),
        icon=str(raw.get("icon") or ""),
        category=str(raw.get("category") or ""),
        vendor=str(raw.get("vendor") or ""),
        permissions=cleaned_permissions,
        menus=cleaned_menus,
        manifest_version=manifest_version,
        schema_version=int(raw.get("schema_version") or 0),
        min_core_version=min_core,
        max_core_version=max_core,
        product=str(raw.get("product") or ""),
        dev_method=str(raw.get("dev_method") or ""),
        data={**data, "retention": retention, "tables": tables},
        tasks={"celery": list(tasks.get("celery") or []), "beat": list(tasks.get("beat") or [])},
        dependencies=dependencies,
        changelog=str(raw.get("changelog") or ""),
    )
