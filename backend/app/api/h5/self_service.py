# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""员工自助端的放行判定。

按权限码而不是角色名判定：`worker`/`workshop_leader`/`production_manager` 这类自建角色
只要拿到对应权限码，就能正常打卡、看任务、报工、查工资。
"""
from fastapi import HTTPException

from app.models.user import User


TASK_READ = {"task.view", "task.manage", "dispatch.manage", "report.submit", "qc.inspect"}
REPORT_READ = {"report.submit", "report.view", "report.audit", "task.view", "qc.inspect"}
REPORT_SUBMIT = {"report.submit"}
SALARY_VIEW = {"salary.view", "salary.manage"}
SELF_SERVICE = {"report.submit", "task.view", "salary.view", "attendance.manage"}


def ensure_permission(user: User, allowed: set[str]) -> None:
    codes = {p.code for r in user.roles for p in r.permissions}
    if not codes & allowed:
        raise HTTPException(status_code=403, detail="无权限")
