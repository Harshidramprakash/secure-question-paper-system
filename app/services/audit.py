"""Audit logging service — records security-relevant events."""
from datetime import datetime, timezone
from flask import request
from ..extensions import db
from ..models.audit_log import AuditLog


def log_event(user_id=None, action='UNKNOWN', resource_type=None,
              resource_id=None, status='SUCCESS', details=None):
    """Create an immutable audit log entry.

    Args:
        user_id: ID of the user performing the action (None for anonymous).
        action: Short action identifier (e.g. LOGIN_SUCCESS, SECTION_SUBMITTED).
        resource_type: Type of resource affected (e.g. 'user', 'section', 'paper').
        resource_id: ID of the affected resource.
        status: Outcome — SUCCESS, FAILURE, or BLOCKED.
        details: Free-text details about the event.
    """
    ip_address = None
    try:
        ip_address = request.remote_addr
    except RuntimeError:
        pass  # Outside request context (e.g. during testing or CLI)

    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        status=status,
        details=details,
        ip_address=ip_address,
        created_at=datetime.now(timezone.utc),
    )
    db.session.add(entry)
    db.session.commit()
    return entry
