import os
from celery import Celery
from django.conf import settings

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'movie_recommendation.settings')

app = Celery('movie_recommendation')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Celery beat schedule for periodic tasks
app.conf.beat_schedule = {
    'retrain-ml-models': {
        'task': 'recommendations.tasks.retrain_ml_models',
        'schedule': 3600.0,  # Run every hour
    },
    'update-trending-movies': {
        'task': 'recommendations.tasks.update_trending_movies',
        'schedule': 1800.0,  # Run every 30 minutes
    },
    'cleanup-old-recommendations': {
        'task': 'recommendations.tasks.cleanup_old_recommendations',
        'schedule': 86400.0,  # Run daily
    },
}

app.conf.timezone = 'UTC'

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')