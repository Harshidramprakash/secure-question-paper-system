"""Question section model — individually encrypted and integrity-verified."""
from datetime import datetime, timezone
from ..extensions import db


class QuestionSection(db.Model):
    """A single section of a question paper, assigned to one setter.

    Content is stored AES-256-GCM encrypted with a unique nonce.
    A SHA-256 hash of the plaintext is stored for integrity verification.
    """

    __tablename__ = 'question_sections'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    # Section statuses
    STATUS_PENDING = 'PENDING'       # Assigned but not yet submitted
    STATUS_DRAFT = 'DRAFT'           # Setter saved a draft
    STATUS_SUBMITTED = 'SUBMITTED'   # Setter submitted for review
    STATUS_APPROVED = 'APPROVED'     # Admin approved
    STATUS_REJECTED = 'REJECTED'     # Admin rejected

    id = db.Column(db.Integer, primary_key=True)
    paper_id = db.Column(
        db.Integer, db.ForeignKey('question_papers.id'), nullable=False, index=True
    )
    setter_id = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=False, index=True
    )
    section_name = db.Column(db.String(100), nullable=False)
    section_order = db.Column(db.Integer, default=1, nullable=False)

    # Encrypted content — populated on submission
    encrypted_content = db.Column(db.LargeBinary, nullable=True)
    nonce = db.Column(db.LargeBinary, nullable=True)       # 12-byte AES-GCM nonce
    content_hash = db.Column(db.String(64), nullable=True)  # SHA-256 hex digest

    status = db.Column(db.String(20), default=STATUS_PENDING, nullable=False)
    submitted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Relationships
    paper = db.relationship('QuestionPaper', back_populates='sections')
    setter = db.relationship('User', back_populates='assigned_sections')

    def __repr__(self):
        return f'<QuestionSection {self.id}: {self.section_name} [{self.status}]>'
