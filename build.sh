#!/usr/bin/env bash
# Executado pelo Render a cada deploy. Para no primeiro erro.
set -o errexit

pip install --upgrade pip
pip install -r requirements/base.txt

python manage.py collectstatic --no-input
python manage.py migrate --no-input
python manage.py create_owner_group
python manage.py seed_bot_replies