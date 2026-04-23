import os

from celery import Celery

from django.conf import settings

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

app = Celery('myproject')

# Load settings from Django's settings.py (only keys starting with 'CELERY_')
app.config_from_object('django.conf:settings', namespace='CELERY_')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Timezone configuration
app.conf.timezone = getattr(settings, 'TIME_ZONE', 'Asia/Kathmandu')
app.conf.enable_utc = False  # Use local time instead of UTC