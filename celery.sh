#!/bin/bash

celery -A server.celery_app worker --beat -l debug
