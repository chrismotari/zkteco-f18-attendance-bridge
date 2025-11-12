#!/bin/bash

# Start Celery Worker
celery -A attendance_bridge worker --loglevel=info
