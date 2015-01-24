#!/bin/bash

celery worker -A server.celery_app -B --autoreload &
#celery -A server.celery_app worker --beat -l debug
#celery -A scheduler worker --beat -l debug
