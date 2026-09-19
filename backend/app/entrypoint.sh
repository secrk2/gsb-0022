#!/bin/sh
set -e

case "${1:-web}" in
  web)
    python manage.py wait_for_es
    exec gunicorn guanlan.wsgi:application \
      --bind 0.0.0.0:7121 \
      --workers 2 \
      --timeout 60 \
      --access-logfile - \
      --error-logfile -
    ;;
  consumer)
    python manage.py wait_for_es
    exec python manage.py consume_logs
    ;;
  *)
    exec "$@"
    ;;
esac
