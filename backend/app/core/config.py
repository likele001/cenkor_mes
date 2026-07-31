from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "CenkorMES Backend"
    APP_ENV: str = "dev"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    DB_URL: str = "mysql+pymysql://root:root@127.0.0.1:3306/cenkormes?charset=utf8mb4"
    DB_ECHO: bool = False
    DB_AUTO_CREATE: bool = True
    DB_AUTO_SEED: bool = True

    JWT_SECRET: str = "change_me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    REMEMBER_ME_EXPIRE_MINUTES: int = 10080
    PUBLIC_BASE_URL: str = ""
    H5_PUBLIC_BASE_URL: str = ""

    STORAGE_DRIVER: str = "local"
    STORAGE_LOCAL_ROOT: str = "./data/storage"
    FILE_MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024
    FILE_ALLOWED_MIME: str = (
        "image/jpeg,image/png,image/webp,application/pdf,"
        "video/mp4,video/quicktime,video/webm,video/3gpp,video/x-msvideo"
    )

    REDIS_URL: str = "redis://127.0.0.1:6379/0"
    CELERY_BROKER_URL: str = "redis://127.0.0.1:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://127.0.0.1:6379/1"
    CELERY_TIMEZONE: str = "Asia/Shanghai"
    CELERY_ENABLE_UTC: bool = True


settings = Settings()
