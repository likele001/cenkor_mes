import uvicorn

from app.core.config import settings


def run():
    uvicorn.run("app.main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=settings.APP_ENV == "dev")


if __name__ == "__main__":
    run()

