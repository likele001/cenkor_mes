"""公开溯源：附件查询参数"""

from app.crud.attachment import get_attachment_by_id


def test_get_attachment_by_id_keyword_only(session, tenant):
    """get_attachment_by_id 仅接受关键字参数 tenant_id / attachment_id。"""
    assert get_attachment_by_id(session, tenant_id=tenant.id, attachment_id=99999) is None
