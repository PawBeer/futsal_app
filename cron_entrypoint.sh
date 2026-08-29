#!/bin/sh
set -e

# Idempotent: safe to run again even though the gunicorn container already
# migrates on boot, this just guards against startup ordering between containers.
python manage.py migrate --noinput

# send_weekly_reminders, send_standby_reminders and check_minimum_players are
# themselves idempotent (guarded by each GameNotification's sent_at/send_at),
# so polling them on an interval is enough - no real cron daemon needed. 900s
# keeps reminder timing accurate to within 15 minutes.
while true; do
    python manage.py send_weekly_reminders
    python manage.py send_standby_reminders
    python manage.py check_minimum_players
    sleep 900
done
