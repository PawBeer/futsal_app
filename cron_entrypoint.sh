#!/bin/sh
set -e

# Idempotent: safe to run again even though the gunicorn container already
# migrates on boot, this just guards against startup ordering between containers.
python manage.py migrate --noinput

# send_weekly_reminders is itself idempotent (guarded by Game.reminder_sent_at
# and Game.reminder_send_at), so polling it on an interval is enough - no real
# cron daemon needed. 900s keeps reminder timing accurate to within 15 minutes.
while true; do
    python manage.py send_weekly_reminders
    sleep 900
done
