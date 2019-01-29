#!/usr/bin/env sh
gunicorn --bind 0.0.0.0:80 --workers 40 wsgi
