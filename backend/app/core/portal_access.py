"""区分管理后台入口与 H5 入口的账号能力。"""

from app.models.user import User

H5_PORTAL_ROLE_CODES = frozenset({"employee", "customer"})
ADMIN_PORTAL_HEADER = "X-CenkorMES-Portal"
ADMIN_PORTAL_VALUE = "admin"


def user_role_codes(user: User) -> set[str]:
    return {r.code for r in (user.roles or [])}


def is_h5_portal_user(user: User) -> bool:
    if user.is_superuser:
        return False
    roles = user_role_codes(user)
    if not roles:
        return True
    return roles.issubset(H5_PORTAL_ROLE_CODES)
