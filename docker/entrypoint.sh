#!/usr/bin/env bash
set -euo pipefail

echo "[entrypoint] starting backend bootstrap"

python - <<'PY'
import os
import time
from sqlalchemy import create_engine, text

db_url = os.getenv("DATABASE_URL")
if not db_url:
    raise SystemExit("DATABASE_URL is not set")

last_err = None
for attempt in range(1, 31):
    try:
        engine = create_engine(db_url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print(f"[entrypoint] database ready on attempt {attempt}")
        break
    except Exception as exc:
        last_err = exc
        print(f"[entrypoint] waiting for database ({attempt}/30): {exc}")
        time.sleep(2)
else:
    raise SystemExit(f"Database not reachable after retries: {last_err}")
PY

echo "[entrypoint] running migrations"
if flask --app run:app db upgrade >/tmp/flask_migrate.log 2>&1; then
  echo "[entrypoint] flask db upgrade completed"
else
    echo "[entrypoint] flask db upgrade failed; retrying with all heads"
    if flask --app run:app db upgrade heads >/tmp/flask_migrate_heads.log 2>&1; then
        echo "[entrypoint] flask db upgrade heads completed"
    else
        echo "[entrypoint] flask db upgrade heads failed; continuing with schema fallback"
        echo "[entrypoint] migration error summary:"
        tail -n 5 /tmp/flask_migrate_heads.log || tail -n 5 /tmp/flask_migrate.log || true
    fi
fi

echo "[entrypoint] ensuring tables exist"
python - <<'PY'
from app import create_app
from app.extensions import db
from sqlalchemy import inspect

app = create_app()
with app.app_context():
    db.create_all()
    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())
    required = {"users", "sessions"}
    missing = sorted(required - tables)
    if missing:
        print(f"[entrypoint] warning: missing required tables after bootstrap: {missing}")
    else:
        print("[entrypoint] required tables present")
PY

echo "[entrypoint] starting gunicorn"
exec gunicorn run:app
