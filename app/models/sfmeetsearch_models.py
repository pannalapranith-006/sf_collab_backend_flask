from datetime import datetime
from app import db


class Meeting(db.Model):
    __tablename__ = 'sfmeet_meetings'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Transcript(db.Model):
    __tablename__ = 'sfmeet_transcripts'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, nullable=False, index=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey('sfmeet_meetings.id'))

    content = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Summary(db.Model):
    __tablename__ = 'sfmeet_summaries'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, nullable=False, index=True)
    meeting_id = db.Column(db.Integer)

    content = db.Column(db.Text)


class Decision(db.Model):
    __tablename__ = 'sfmeet_decisions'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, nullable=False, index=True)
    meeting_id = db.Column(db.Integer)

    content = db.Column(db.Text)