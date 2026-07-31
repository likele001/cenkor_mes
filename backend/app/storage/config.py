from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CloudDriverConfig:
    endpoint: str = ""
    region: str = ""
    bucket: str = ""
    access_key: str = ""
    secret_key: str = ""
    custom_domain: str = ""


@dataclass(frozen=True)
class StorageConfig:
    enabled: bool
    driver: str
    local_root: str
    aliyun_oss: CloudDriverConfig
    tencent_cos: CloudDriverConfig
    qiniu: CloudDriverConfig
