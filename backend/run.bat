@echo off
cd /d %~dp0
start "celery-worker" /b python -m celery -A app.celery_app.celery worker -l info
start "celery-beat" /b python -m celery -A app.celery_app.celery beat -l info
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
