"""当前登录用户资料与密码（租户用户 / 平台用户共用校验逻辑）。"""

from app.schemas.profile import ProfileUpdateIn


def profile_fields_to_update(payload: ProfileUpdateIn) -> dict:
    """仅更新请求体中显式传入的字段。"""
    data = payload.model_dump(exclude_unset=True)
    out: dict = {}
    if "full_name" in data:
        out["full_name"] = data["full_name"]
    if "phone" in data:
        out["phone"] = data["phone"]
    if "email" in data:
        out["email"] = data["email"]
    return out
