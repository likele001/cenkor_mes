from __future__ import annotations

"""飞书推送链接构建"""

from app.core.config import settings as app_settings

from typing import Any


def _h5_deep_link(h5_base: str, subpath: str, **query: Any) -> str:
    """拼 H5 深链 + query 参数（单租户版无 /t/{code}/ 前缀）"""
    base = h5_base.rstrip("/")
    qs = "&".join(f"{k}={v}" for k, v in query.items() if v is not None and v != "")
    sep = "&" if "?" in subpath else "?"
    url = f"{base}{subpath}"
    if qs:
        url = f"{url}{sep}{qs}" if "?" not in subpath else f"{url}&{qs}"
    return url


def build_message_urls(
    cfg: dict,
    *,
    event_code: str,
    biz_type: str | None,
    biz_id: int | None,
    task_code: str | None = None,
) -> tuple[str | None, str | None]:
    h5_base = (cfg.get("h5_public_base_url") or app_settings.H5_PUBLIC_BASE_URL or "").strip().rstrip("/")
    admin_base = (cfg.get("admin_public_base_url") or "").strip().rstrip("/")
    h5_url = None
    admin_url = None

    if event_code == "dispatch.assigned" and h5_base:
        # 派工卡片：有 task_code 时直接跳报工页，否则兜底跳任务列表
        if task_code:
            h5_url = _h5_deep_link(h5_base, "/report-unit", task_code=task_code)
        else:
            h5_url = _h5_deep_link(h5_base, "/tasks")
    elif event_code.startswith("report") and biz_type in ("report", "report_unit"):
        if h5_base:
            subpath = "/report-units" if biz_type == "report_unit" else "/tasks"
            h5_url = _h5_deep_link(h5_base, subpath)
        if admin_base and biz_id:
            # 报工待审卡片：带 focus_id 让 Admin 端自动开 dialog
            admin_path = "/production/report-units" if biz_type == "report_unit" else "/production/reports"
            admin_url = f"{admin_base}{admin_path}?focus_id={int(biz_id)}"
        elif event_code == "report.submitted" and admin_base:
            admin_url = f"{admin_base}/production/reports"
    elif event_code.startswith("salary") and h5_base:
        h5_url = _h5_deep_link(h5_base, "/salary-slips")
    elif event_code.startswith("order") and admin_base:
        admin_url = f"{admin_base}/production/orders"
        if biz_type == "order" and biz_id:
            admin_url = f"{admin_base}/production/orders?keyword={biz_id}"
    elif event_code.startswith("crm.") and admin_base:
        if biz_type == "crm_opportunity" and biz_id:
            admin_url = f"{admin_base}/crm/opportunities"
        else:
            admin_url = f"{admin_base}/crm/opportunities"
    elif event_code.startswith("after_sale") and admin_base:
        admin_url = f"{admin_base}/crm/after-sales"
        if h5_base and biz_type == "after_sale":
            h5_url = _h5_deep_link(h5_base, "/orders")
    elif event_code.startswith("statement") and admin_base:
        admin_url = f"{admin_base}/finance/statements"
        if biz_type == "statement" and biz_id:
            admin_url = f"{admin_base}/finance/statements/{biz_id}"
    elif event_code == "brief.daily" and admin_base:
        admin_url = f"{admin_base}/home"
    elif admin_base and biz_type:
        admin_url = admin_base

    return h5_url, admin_url
