"""Question paper model."""
from datetime import datetime, timezone
from ..extensions import db


class QuestionPaper(db.Model):
    """An examination question paper composed of multiple sections."""

    __tablename__ = 'question_papers'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    # Paper statuses
    STATUS_DRAFT = 'DRAFT'
    STATUS_SECTIONS_ASSIGNED = 'SECTIONS_ASSIGNED'
    STATUS_UNDER_REVIEW = 'UNDER_REVIEW'
    STATUS_APPROVED = 'APPROVED'
    STATUS_READY_FOR_RELEASE = 'READY_FOR_RELEASE'
    STATUS_RELEASED = 'RELEASED'
    STATUS_REVOKED = 'REVOKED'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    exam_date = db.Column(db.Date, nullable=False)
    release_time = db.Column(db.DateTime(timezone=True), nullable=False)
    status = db.Column(db.String(30), default=STATUS_DRAFT, nullable=False)
    
    # Assembled encrypted content (Populated during assembly)
    encrypted_content = db.Column(db.LargeBinary, nullable=True)
    nonce = db.Column(db.LargeBinary, nullable=True)
    content_hash = db.Column(db.String(64), nullable=True)
    
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    sections = db.relationship(
        'QuestionSection', back_populates='paper', lazy='dynamic',
        cascade='all, delete-orphan'
    )
    approvals = db.relationship(
        'Approval', back_populates='paper', lazy='dynamic',
        cascade='all, delete-orphan'
    )
    creator = db.relationship('User', foreign_keys=[created_by])

    @property
    def total_sections(self):
        return self.sections.count()

    @property
    def approved_sections(self):
        from .question_section import QuestionSection
        return self.sections.filter_by(status=QuestionSection.STATUS_APPROVED).count()

    @property
    def all_sections_approved(self):
        total = self.total_sections
        return total > 0 and self.approved_sections == total

    def __repr__(self):
        return f'<QuestionPaper {self.id}: {self.title}>'
