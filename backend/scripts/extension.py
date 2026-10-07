# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""扩展包管理 CLI（MES 宿主侧；管理动作的正源在独立应用中心）。

用法（在 backend/ 目录下运行）::

    python scripts/extension.py list                # 列出已安装扩展及状态
    python scripts/extension.py install <zip路径>   # 本地安装扩展包（校验 manifest）
    python scripts/extension.py enable <key>        # 本地启用（清除 disabled 覆盖）
    python scripts/extension.py disable <key>       # 本地禁用（覆盖优先于授权）
    python scripts/extension.py remove <key>        # 卸载（删除扩展目录）
    python scripts/extension.py sync                # 立即执行一次应用中心授权同步

注意：安装/启用/卸载后需重启后端进程，路由与前端插件才会生效。
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.extension_host.host import extensions_base_dir  # noqa: E402
from app.extension_host.manifest import ManifestError, load_manifest  # noqa: E402
from app.extension_host.state import StateStore  # noqa: E402


def _load_state() -> tuple[Path, StateStore]:
    """读取扩展目录与状态存储（轻量，不启动 FastAPI）。"""
    base = extensions_base_dir()
    base.mkdir(parents=True, exist_ok=True)
    return base, StateStore(base / ".state")


def cmd_list(_: argparse.Namespace) -> int:
    """列出已安装扩展与状态。"""
    base, store = _load_state()
    overrides = store.load("overrides", {}) or {}
    found = False
    for child in sorted(base.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        try:
            manifest = load_manifest(child)
        except ManifestError as e:
            print(f"  [非法] {child.name}: {e}")
            continue
        found = True
        state = "disabled(本地)" if overrides.get(manifest.key) == "disabled" else "enabled"
        print(f"  {manifest.key:24s} v{manifest.version:10s} {state:14s} {manifest.name}")
    if not found:
        print(f"（{base} 下暂无扩展；可用 install 子命令安装 zip 包）")
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    """解压安装扩展包（zip 内须含 manifest.json，位于包根或单层子目录）。"""
    base, _store = _load_state()
    zip_path = Path(args.zip).resolve()
    if not zip_path.is_file():
        print(f"包不存在: {zip_path}")
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        try:
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(root)
        except zipfile.BadZipFile:
            print("不是有效的 zip 包")
            return 1
        if not (root / "manifest.json").is_file():
            subs = [d for d in root.iterdir() if d.is_dir()]
            if len(subs) == 1 and (subs[0] / "manifest.json").is_file():
                root = subs[0]
        try:
            manifest = load_manifest(root, check_dir_name=False)
        except ManifestError as e:
            print(f"manifest 校验失败: {e}")
            return 1
        target = base / manifest.key
        if target.exists():
            print(f"扩展 {manifest.key} 已存在（先 remove 再 install）")
            return 1
        shutil.copytree(root, target)
        try:
            load_manifest(target)  # 落位后再校验一次（目录名一致性）
        except ManifestError as e:
            shutil.rmtree(target)
            print(f"安装校验失败，已回滚: {e}")
            return 1
    print(f"已安装 {manifest.key} v{manifest.version} → {target}")
    print("提示：重启后端进程后路由与前端插件生效")
    return 0


def cmd_enable(args: argparse.Namespace) -> int:
    """本地启用（清除 disabled 覆盖；授权仍以应用中心为准）。"""
    _base, store = _load_state()
    overrides = store.load("overrides", {}) or {}
    if overrides.pop(args.key, None) is None:
        print(f"{args.key} 无本地禁用记录；如未生效请检查应用中心授权状态")
    else:
        store.save("overrides", overrides)
        print(f"已启用 {args.key}（本地覆盖已清除）")
    return 0


def cmd_disable(args: argparse.Namespace) -> int:
    """本地禁用（覆盖优先于授权）。"""
    _base, store = _load_state()
    overrides = store.load("overrides", {}) or {}
    overrides[args.key] = "disabled"
    store.save("overrides", overrides)
    print(f"已禁用 {args.key}（本地覆盖优先于授权；重启后端后路由移除）")
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    """卸载扩展（删除目录并清除本地覆盖）。"""
    base, store = _load_state()
    target = base / args.key
    if not target.is_dir():
        print(f"扩展不存在: {target}")
        return 1
    shutil.rmtree(target)
    overrides = store.load("overrides", {}) or {}
    if overrides.pop(args.key, None) is not None:
        store.save("overrides", overrides)
    print(f"已卸载 {args.key}（重启后端后路由移除）")
    return 0


def cmd_sync(_: argparse.Namespace) -> int:
    """立即执行一次应用中心授权同步。"""
    from app.extension_host import loader
    from app.extension_host.state import runtime
    from app.extension_host.sync import sync_once

    base, store = _load_state()
    runtime.store = store
    runtime.load_from_disk()
    runtime.installed = loader.scan_extensions(base)

    if not runtime.center_configured:
        print("未配置应用中心（APP_CENTER_URL / APP_CENTER_INSTANCE_UID / APP_CENTER_INSTANCE_TOKEN），当前为本地模式")
        return 1
    if sync_once():
        print(f"同步成功：授权 {len(runtime.entitlements)} 项，时间 {runtime.synced_at}")
        print("提示：运行中的后端会在周期同步中自动生效；如需立即生效请重启后端")
        return 0
    print("同步失败（保留旧快照），请检查网络与中心地址/实例令牌")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="CenkorMES 扩展包管理 CLI（宿主侧）")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="列出已安装扩展及状态")

    p_install = sub.add_parser("install", help="安装扩展包（zip，含 manifest.json）")
    p_install.add_argument("zip", help="zip 包路径")

    p_enable = sub.add_parser("enable", help="本地启用扩展（清除 disabled 覆盖）")
    p_enable.add_argument("key", help="扩展 key")

    p_disable = sub.add_parser("disable", help="本地禁用扩展（覆盖优先于授权）")
    p_disable.add_argument("key", help="扩展 key")

    p_remove = sub.add_parser("remove", help="卸载扩展（删除目录）")
    p_remove.add_argument("key", help="扩展 key")

    sub.add_parser("sync", help="立即执行一次应用中心授权同步")

    args = parser.parse_args()
    handlers = {
        "list": cmd_list,
        "install": cmd_install,
        "enable": cmd_enable,
        "disable": cmd_disable,
        "remove": cmd_remove,
        "sync": cmd_sync,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
