from datetime import datetime
from app.extensions import db


class Vision(db.Model):
    __tablename__ = "visions"

    id = db.Column(db.Integer, primary_key=True)

    # 🔗 Creator (Founder)
    creator_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    creator = db.relationship("User", backref=db.backref("visions", lazy=True))

    # 📌 Core Vision Info
    title = db.Column(db.String(255), nullable=False)
    problem_statement = db.Column(db.Text, nullable=False)
    solution = db.Column(db.Text, nullable=False)

    # 🧠 Matching Signals
    sector = db.Column(db.String(100), nullable=True)

    # Store as JSON arrays
    technologies = db.Column(db.JSON, default=[])
    roles_needed = db.Column(db.JSON, default=[])

    # Example:
    # roles_needed = ["ML Engineer", "Backend Developer"]

    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "creator_id": self.creator_id,
            "title": self.title,
            "problem_statement": self.problem_statement,
            "solution": self.solution,
            "sector": self.sector,
            "technologies": self.technologies or [],
            "roles_needed": self.roles_needed or [],
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }