from datetime import date
from app import db
from app.models.daily_update import DailyUpdate

def submit_update(workspace_id, user_id, content):
    """Create or update today's daily update. Raises ValueError if missing."""
    if not content or not content.strip():
        raise ValueError('Content cannot be empty.')

    today = date.today()
    existing = DailyUpdate.query.filter_by(
        user_id=user_id,
        workspace_id=workspace_id,
        log_date=today
    ).first()

    if existing:
        existing.content = content
        db.session.commit()
        return existing
    else:
        entry = DailyUpdate(
            user_id=user_id,
            workspace_id=workspace_id,
            log_date=today,
            content=content
        )
        db.session.add(entry)
        db.session.commit()
        return entry

def get_updates(workspace_id, user_id=None, start_date=None, end_date=None):
    """
    Get daily updates for a workspace. Optionally filter by user or date range.
    Returns list of entries ordered by date descending.
    """
    query = DailyUpdate.query.filter_by(workspace_id=workspace_id)

    if user_id:
        query = query.filter_by(user_id=user_id)

    if start_date:
        query = query.filter(DailyUpdate.log_date >= start_date)
    if end_date:
        query = query.filter(DailyUpdate.log_date <= end_date)

    return query.order_by(DailyUpdate.log_date.desc()).all()