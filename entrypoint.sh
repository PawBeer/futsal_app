#!/bin/sh
set -e

python manage.py migrate --noinput
python manage.py collectstatic --noinput

gunicorn futsal_app.wsgi:application --bind 0.0.0.0:8000
