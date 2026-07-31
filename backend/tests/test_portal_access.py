from types import SimpleNamespace

from app.core.portal_access import is_h5_portal_user


def _user(*role_codes: str, is_superuser: bool = False):
    roles = [SimpleNamespace(code=c) for c in role_codes]
    return SimpleNamespace(is_superuser=is_superuser, roles=roles)


def test_employee_is_h5_only():
    assert is_h5_portal_user(_user("employee")) is True


def test_customer_is_h5_only():
    assert is_h5_portal_user(_user("customer")) is True


def test_leader_can_use_admin():
    assert is_h5_portal_user(_user("leader")) is False


def test_admin_can_use_admin():
    assert is_h5_portal_user(_user("admin")) is False


def test_employee_with_leader_can_use_admin():
    assert is_h5_portal_user(_user("employee", "leader")) is False


def test_superuser_can_use_admin():
    assert is_h5_portal_user(_user("employee", is_superuser=True)) is False
