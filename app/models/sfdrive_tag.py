from datetime import datetime
from app.extensions import db


class Tag(db.Model):
    __tablename__ = 'sf_tags'

    id = db.Column(db.Integer, primary_key=True)

    file_id = db.Column(
        db.Integer,
        db.ForeignKey('sf_files.id'),
        nullable=False
    )

    tag_name = db.Column(db.String(100), nullable=False)

    tag_type = db.Column(
        db.String(50),
        default='manual'
    )
    # manual / system / ai

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )