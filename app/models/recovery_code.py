"""Recovery Code model for MFA backup access."""
from datetime import datetime, timezone
from ..extensions import db


class RecoveryCode(db.Model):
    """Stores hashed backup codes for account recovery."""
    
    __tablename__ = 'recovery_codes'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    code_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    
    # Relationship
    user = db.relationship('User', back_populates='recovery_codes')

    def __repr__(self):
        return f'<RecoveryCode for User ID {self.user_id}>'
