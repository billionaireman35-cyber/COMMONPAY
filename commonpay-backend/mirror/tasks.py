import asyncio, os
from celery import Celery

celery_app = Celery("commonpay", broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"))
celery_app.conf.timezone = "UTC"
celery_app.conf.task_ignore_result = True
celery_app.conf.beat_schedule = {
    "mirror-sweep": {"task": "mirror.sweep", "schedule": float(os.getenv("MIRROR_SWEEP_SECONDS", "600"))},
}

@celery_app.task(name="mirror.sweep")
def sweep_task():
    from mirror.sweep import run
    return asyncio.run(run())
