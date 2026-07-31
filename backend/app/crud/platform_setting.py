from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.platform_setting import PlatformSetting

DEFAULTS = {
    "saas_mode_enabled": "false",
    "xunhu_app_id": "",
    "xunhu_app_secret": "",
    "xunhu_gateway": "https://api.xunhupay.com/payment/do.html",
    "default_trial_days": "14",
    # 注册成功后跳转（勿填 register 站，应填 admin / h5 / portal 对外域名）
    "admin_site_url": "",
    "h5_site_url": "",
    "portal_site_url": "",
    # 开启后：管理端登录、H5 登录、平台总控登录、邀请注册、企业自助注册均需验证码
    "login_captcha_enabled": "false",
    "storage_enabled": "false",
    "storage_driver": "local",
    "storage_aliyun_oss_endpoint": "",
    "storage_aliyun_oss_region": "",
    "storage_aliyun_oss_bucket": "",
    "storage_aliyun_oss_access_key": "",
    "storage_aliyun_oss_secret_key": "",
    "storage_aliyun_oss_custom_domain": "",
    "storage_tencent_cos_endpoint": "",
    "storage_tencent_cos_region": "",
    "storage_tencent_cos_bucket": "",
    "storage_tencent_cos_access_key": "",
    "storage_tencent_cos_secret_key": "",
    "storage_tencent_cos_custom_domain": "",
    "storage_qiniu_endpoint": "",
    "storage_qiniu_region": "",
    "storage_qiniu_bucket": "",
    "storage_qiniu_access_key": "",
    "storage_qiniu_secret_key": "",
    "storage_qiniu_custom_domain": "",
}


def get_setting(db: Session, key: str) -> str | None:
    row = db.scalar(select(PlatformSetting).where(PlatformSetting.key == key))
    if row is None:
        return DEFAULTS.get(key)
    return row.value


def get_bool_setting(db: Session, key: str) -> bool:
    v = get_setting(db, key)
    return str(v or "").lower() in ("1", "true", "yes", "on")


def set_setting(db: Session, key: str, value: str | None) -> None:
    row = db.scalar(select(PlatformSetting).where(PlatformSetting.key == key))
    if row is None:
        db.add(PlatformSetting(key=key, value=value))
    else:
        row.value = value
    db.flush()


def get_all_settings(db: Session) -> dict[str, str]:
    rows = db.scalars(select(PlatformSetting)).all()
    out = dict(DEFAULTS)
    for r in rows:
        if r.value is not None:
            out[r.key] = r.value
    return out


def is_saas_mode_enabled(db: Session) -> bool:
    return get_bool_setting(db, "saas_mode_enabled")


def is_register_enabled(db: Session) -> bool:
    return is_saas_mode_enabled(db)
