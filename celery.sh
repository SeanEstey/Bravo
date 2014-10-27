#!/bin/bash

export C_FORCE_ROOT=“1”:$C_FORCE_ROOT
celery -A tasks worker
