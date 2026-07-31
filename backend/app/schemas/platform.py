from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class PlatformLoginIn(BaseModel):
    username: str
    password: str
    remember_me: bool = False
    captcha_id: str | None = None
    captcha_code: str | None = None


class CloudStorageDriverIn(BaseModel):
    endpoint: str | None = None
    region: str | None = None
    bucket: str | None = None
    access_key: str | None = None
    secret_key: str | None = None
    custom_domain: str | None = None


class PlatformStorageSettingsIn(BaseModel):
    storage_enabled: bool | None = None
    storage_driver: str | None = Field(default=None, max_length=32)
    storage_local_backup_enabled: bool | None = None
    storage_local_backup_root: str | None = Field(default=None, max_length=256)
    aliyun_oss: CloudStorageDriverIn | None = None
    tencent_cos: CloudStorageDriverIn | None = None
    qiniu: CloudStorageDriverIn | None = None


class PlatformSettingsIn(BaseModel):
    login_captcha_enabled: bool | None = None
    saas_mode_enabled: bool | None = None
    xunhu_app_id: str | None = None
    xunhu_app_secret: str | None = None
    xunhu_gateway: str | None = None
    default_trial_days: int | None = None
    admin_site_url: str | None = None
    h5_site_url: str | None = None
    portal_site_url: str | None = None


class PlatformStorageTestIn(BaseModel):
    driver: str | None = Field(default=None, max_length=32)


class SaasPackageIn(BaseModel):
    code: str | None = Field(default=None, max_length=32)
    name: str = Field(min_length=1, max_length=128)
    price_yuan: Decimal = Field(ge=0)
    duration_days: int = Field(ge=1, le=3650)
    max_users: int = Field(ge=1, le=10000)
    features_json: str | None = None
    description: str | None = None
    sort_order: int = 0
    is_active: bool = True
    # 6月24日新增字段（与 alembic 0066/0067 对齐）
    tier: str = Field(default="pro", max_length=32)
    delivery_mode: str = Field(default="saas", max_length=16)
    max_industries: int = Field(default=-1, ge=-1, le=20)
    allowed_industry_codes: str | None = None  # JSON 列表，null = 不限


class SaasPackageUpdateIn(BaseModel):
    name: str | None = None
    price_yuan: Decimal | None = None
    duration_days: int | None = None
    max_users: int | None = None
    features_json: str | None = None
    description: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None
    # 6月24日新增
    tier: str | None = Field(default=None, max_length=32)
    delivery_mode: str | None = Field(default=None, max_length=16)
    max_industries: int | None = Field(default=None, ge=-1, le=20)
    allowed_industry_codes: str | None = None


class PlatformTenantCreateIn(BaseModel):
    tenant_code: str = Field(min_length=1, max_length=32)
    tenant_name: str = Field(min_length=1, max_length=128)
    admin_username: str = Field(min_length=1, max_length=64)
    admin_password: str = Field(min_length=6, max_length=128)
    admin_full_name: str | None = Field(default=None, max_length=128)
    package_id: int | None = None
    subscription_expires_at: datetime | None = None
    status: str = "active"


class PlatformTenantUpdateIn(BaseModel):
    tenant_name: str | None = None
    status: str | None = None
    subscription_expires_at: datetime | None = None
    current_package_id: int | None = None


class TenantInviteCreateIn(BaseModel):
    role_code: str = "employee"
    max_uses: int = Field(default=10, ge=1, le=1000)
    expires_days: int | None = Field(default=7, ge=1, le=365)


class RegisterByInviteIn(BaseModel):
    token: str
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    full_name: str | None = None
    captcha_id: str | None = Field(default=None, max_length=64)
    captcha_code: str | None = Field(default=None, max_length=16)
