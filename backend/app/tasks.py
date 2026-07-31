"""Celery tasks – CenkorMES."""
from celery import shared_task
from app.tasks.salary import calculate_salary_items, generate_salary_slips
from app.tasks.report_exports import export_production_report


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def task_calculate_salary(self, month: str | None = None):
    return calculate_salary_items(month)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def task_generate_salary_slips(self, month: str | None = None):
    return generate_salary_slips(month)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def task_export_production_report(self, export_job_id: int):
    return export_production_report(export_job_id)
