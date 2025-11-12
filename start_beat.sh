#!/bin/bash

# Start Celery Beat (scheduler)
celery -A attendance_bridge beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
