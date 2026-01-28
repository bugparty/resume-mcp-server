from __future__ import annotations

import os

from celery import Celery


def _get_celery_broker_url() -> str:
    return os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")


def _get_celery_result_backend() -> str:
    return os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")


celery_app = Celery(
    "latex_compile_api",
    broker=_get_celery_broker_url(),
    backend=_get_celery_result_backend(),
)

celery_app.conf.update(
    task_track_started=True,
    task_time_limit=int(os.getenv("CELERY_TASK_TIME_LIMIT", "120")),
    task_soft_time_limit=int(os.getenv("CELERY_TASK_SOFT_TIME_LIMIT", "90")),
)
