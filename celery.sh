#!/bin/bash

celery worker -A server.celery_app -f celery.log -B --autoreload &
