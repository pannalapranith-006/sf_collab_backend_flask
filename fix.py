from app import create_app
from app.extensions import db
from sqlalchemy import text
app = create_app()
ctx = app.app_context()
ctx.push()
with db.engine.connect() as conn:
    print(conn.execute(text('SELECT * FROM alembic_version')).fetchall())
    conn.execute(text('DELETE FROM alembic_version'))
    conn.execute(text("INSERT INTO alembic_version VALUES ('03f8e9943718')"))
    conn.commit()
print('Done')
