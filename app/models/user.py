"""User model with password hashing and TOTP MFA support."""
from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from ..extensions import db


class User(UserMixin, db.Model):
    """Application user with role-based access and optional MFA."""

    __tablename__ = 'users'

    # Allowed roles
    ROLE_SETTER_A = 'setter_a'
    ROLE_SETTER_B = 'setter_b'
    ROLE_ADMIN = 'admin'
    ROLE_OFFICER = 'officer'
    VALID_ROLES = (ROLE_SETTER_A, ROLE_SETTER_B, ROLE_ADMIN, ROLE_OFFICER)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    mfa_enabled = db.Column(db.Boolean, default=False, nullable=False)
    mfa_secret = db.Column(db.String(32), nullable=True)  # Base32-encoded TOTP secret
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    assigned_sections = db.relationship(
        'QuestionSection', back_populates='setter', lazy='dynamic'
    )
    approvals = db.relationship(
        'Approval', back_populates='approver', lazy='dynamic'
    )
    audit_logs = db.relationship(
        'AuditLog', back_populates='user', lazy='dynamic'
    )
    recovery_codes = db.relationship(
        'RecoveryCode', back_populates='user', lazy='dynamic', cascade='all, delete-orphan'
    )

    def set_password(self, password):
        """Hash and store a password. Never stores plaintext."""
        self.password_hash = generate_password_hash(
            password, method='scrypt', salt_length=16
        )

    def check_password(self, password):
        """Verify a password against the stored hash."""
        return check_password_hash(self.password_hash, password)

    @property
    def is_setter(self):
        return self.role in (self.ROLE_SETTER_A, self.ROLE_SETTER_B)

    @property
    def is_admin(self):
        return self.role == self.ROLE_ADMIN

    @property
    def is_officer(self):
        return self.role == self.ROLE_OFFICER

    @property
    def role_display(self):
        """Human-readable role name."""
        names = {
            self.ROLE_SETTER_A: 'Question Setter A',
            self.ROLE_SETTER_B: 'Question Setter B',
            self.ROLE_ADMIN: 'Administrator',
            self.ROLE_OFFICER: 'Examination Officer',
        }
        return names.get(self.role, self.role)

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'
