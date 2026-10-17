#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$PROJECT_DIR/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
    printf 'Python environment not found: %s\n' "$PYTHON" >&2
    exit 1
fi

cd "$PROJECT_DIR"
"$PYTHON" -m pip install -r requirements.txt
"$PYTHON" manage.py migrate --noinput
"$PYTHON" manage.py collectstatic --noinput
sudo chgrp -R www-data "$PROJECT_DIR/config" "$PROJECT_DIR/storefront"
sudo chmod -R g+rX "$PROJECT_DIR/config" "$PROJECT_DIR/storefront"
sudo apache2ctl configtest
sudo systemctl restart apache2