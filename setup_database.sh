#!/bin/bash

# Database Setup Script for SF Collab Backend
# Runs migrations first, then creates any missing tables as fallback.

set -euo pipefail

echo "Starting database setup..."

if [ -d "venv" ]; then
    # shellcheck disable=SC1091
    source venv/bin/activate
fi

export DATABASE_URL="${DATABASE_URL:-mysql+pymysql://sfcollab:sfcollab_pass@localhost:3306/defaultdb}"
echo "Using database: $DATABASE_URL"

echo "Running flask migrations..."
if flask --app run:app db upgrade >/tmp/flask_migrate.log 2>&1; then
    echo "✓ flask db upgrade succeeded"
else
    echo "⚠ flask db upgrade failed; retrying with all heads"
    if flask --app run:app db upgrade heads >/tmp/flask_migrate_heads.log 2>&1; then
        echo "✓ flask db upgrade heads succeeded"
    else
        echo "⚠ flask db upgrade heads failed; proceeding with create_all fallback"
        echo "Migration error summary:"
        tail -n 5 /tmp/flask_migrate_heads.log || tail -n 5 /tmp/flask_migrate.log || true
    fi
fi

python << EOF
from app import create_app
from app.extensions import db
from sqlalchemy import inspect

app = create_app()
with app.app_context():
        print("Ensuring database tables...")
        db.create_all()
        print("✓ db.create_all completed")

        inspector = inspect(db.engine)
        tables = sorted(inspector.get_table_names())
        print(f"✓ Total tables: {len(tables)}")
        print(f"✓ Tables: {', '.join(tables)}")

        required = {"users", "sessions"}
        missing = sorted(required - set(tables))
        if missing:
                raise SystemExit(f"Missing required tables after setup: {missing}")
EOF

echo "Database setup complete!"
