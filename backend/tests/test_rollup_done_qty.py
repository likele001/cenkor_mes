# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""task_done_qty 口径回归：整批报工与件次报工不能重复计数。

背景（2026-11-08 现场）：把 14,461 条件次补成 qc_approved 后，TK000092 计划 300
却显示完成 600。根因是 `production_rollup.task_done_qty()` 把
`reports.good_qty` 与 `report_units` 合格件数相加，而这两者是同一批产出的两种
记法（批量模式写 reports、逐件模式写 report_units）。
"""

from app.models.report import Report
from app.models.report_unit import ReportUnit
from app.services.production_rollup import task_done_qty


def _add_report(session, task, user, good_qty: int, status: str = "qc_approved") -> Report:
    r = Report(
        task_id=task.id,
        report_user_id=user.id,
        good_qty=good_qty,
        bad_qty=0,
        status=status,
    )
    session.add(r)
    session.flush()
    return r


def _add_units(
    session,
    task,
    assignment,
    user,
    count: int,
    *,
    status: str = "qc_approved",
    result_type: str = "good",
    start_seq: int = 1,
) -> None:
    for seq in range(start_seq, start_seq + count):
        session.add(
            ReportUnit(
                task_assignment_id=assignment.id,
                task_id=task.id,
                user_id=user.id,
                unit_seq=seq,
                status=status,
                result_type=result_type,
            )
        )
    session.flush()


def test_batch_only(session, task, test_user):
    """批量模式：只有 reports，完成量 = good_qty。"""
    _add_report(session, task, test_user, good_qty=100)
    assert task_done_qty(session, task.id) == 100


def test_units_only(session, task, assignment, test_user):
    """逐件模式：只有 report_units，完成量 = 合格件数。"""
    _add_units(session, task, assignment, test_user, count=100)
    assert task_done_qty(session, task.id) == 100


def test_same_batch_written_twice_not_doubled(session, task, assignment, test_user):
    """同一批产出既有整批报工又有件次 → 不能翻倍（本次修复的核心场景）。"""
    _add_report(session, task, test_user, good_qty=300)
    _add_units(session, task, assignment, test_user, count=300)
    assert task_done_qty(session, task.id) == 300


def test_pending_units_do_not_count(session, task, assignment, test_user):
    """未终审的件次不计入完成量（含 submitted / leader_approved）。"""
    _add_report(session, task, test_user, good_qty=10)
    _add_units(session, task, assignment, test_user, count=5, status="submitted")
    assert task_done_qty(session, task.id) == 10


def test_bad_units_do_not_count(session, task, assignment, test_user):
    """不良件次不计入完成量。"""
    _add_units(session, task, assignment, test_user, count=7)
    _add_units(session, task, assignment, test_user, count=3, result_type="bad", start_seq=8)
    assert task_done_qty(session, task.id) == 7


def test_explicit_bad_null_result_counts(session, task, assignment, test_user):
    """result_type 为空（历史数据）按合格计，与旧口径保持一致。"""
    _add_units(session, task, assignment, test_user, count=4, result_type=None)  # type: ignore[arg-type]
    assert task_done_qty(session, task.id) == 4


def test_task_status_done_at_planned(session, task, assignment, test_user):
    """完成量达到计划数即置 done，且不会因双计提前完成。"""
    from app.services.production_rollup import sync_task_status

    task.planned_qty = 100
    _add_report(session, task, test_user, good_qty=100)
    _add_units(session, task, assignment, test_user, count=100)
    session.flush()

    assert task_done_qty(session, task.id) == 100
    assert sync_task_status(session, task) == "done"
