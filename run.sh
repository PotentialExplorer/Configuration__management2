#!/bin/sh
# Запуск: ./run.sh [параметры]
cd "$(dirname "$0")" || exit 1
PYTHONPATH=src exec python3 -m depviz "$@"
