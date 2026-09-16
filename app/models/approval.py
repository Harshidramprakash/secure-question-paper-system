"""Approval model — records approval/rejection decisions."""
from datetime import datetime, timezone
from ..extensions import db


class Approval(db.Model):
    """An approval or rejection decision on a section or paper."""

    __tablename__ = 'approvals'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    ACTION_APPROVED = 'APPROVED'
    ACTION_REJECTED = 'REJECTED'
    ACTION_RELEASE_AUTHORIZED = 'RELEASE_AUTHORIZED'

    id = db.Column(db.Integer, primary_key=True)
    paper_id = db.Column(
        db.Integer, db.ForeignKey('question_papers.id'), nullable=False, index=True
    )
    section_id = db.Column(
        db.Integer, db.ForeignKey('question_sections.id'), nullable=True, index=True
    )
    approver_id = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=False, index=True
    )
    action = db.Column(db.String(30), nullable=False)
    comments = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    paper = db.relationship('QuestionPaper', back_populates='approvals')
    section = db.relationship('QuestionSection')
    approver = db.relationship('User', back_populates='approvals')

    def __repr__(self):
        return f'<Approval {self.id}: {self.action} by User {self.approver_id}>'
