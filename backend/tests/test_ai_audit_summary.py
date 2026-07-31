"""审核批量摘要短路测试"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

# scenes 依赖 openai，测试环境可能未安装
sys.modules.setdefault("openai", MagicMock())


@patch("app.services.ai.scenes._run_scene")
@patch("app.crud.report_unit.list_report_units")
def test_audit_batch_summary_empty_skips_llm(mock_list, mock_run):
    from app.services.ai.scenes import audit_batch_summary

    mock_list.return_value = []
    db = MagicMock()
    out = audit_batch_summary(db, tenant_id=1, user_id=1)
    mock_run.assert_not_called()
    assert out["pending_count"] == 0
    assert out["summary"] == "当前无待审记录"
