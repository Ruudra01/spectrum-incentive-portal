#!/usr/bin/env bash
# Vercel build step: install deps and collect static files.
# There is no `migrate` — this project defines no models and uses
# signed-cookie sessions, so it needs no database.
set -euo pipefail
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
python3 manage.py collectstatic --noinput --clear
