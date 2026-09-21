from celery import Celery
from ai_services.config import get_settings
celery_app = Celery("adaptive_engine", broker=get_settings().celery_broker_url, backend=get_settings().redis_url)
