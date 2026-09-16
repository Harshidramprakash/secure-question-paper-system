"""Audit log model — immutable security event records."""
from datetime import datetime, timezone
from ..extensions import db


class AuditLog(db.Model):
    """Immutable record of a security-relevant event.

    Ordinary application users cannot modify or delete audit logs.
    """

    __tablename__ = 'audit_logs'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=True, index=True
    )
    action = db.Column(db.String(100), nullable=False, index=True)
    resource_type = db.Column(db.String(50), nullable=True)
    resource_id = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='SUCCESS')  # SUCCESS / FAILURE / BLOCKED
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # Relationships
    user = db.relationship('User', back_populates='audit_logs')

    def __repr__(self):
        return f'<AuditLog {self.id}: {self.action} [{self.status}]>'
