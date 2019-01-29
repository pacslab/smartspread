#!/usr/bin/env bash
gunicorn --bind 0.0.0.0:80 --workers 4 wsgi