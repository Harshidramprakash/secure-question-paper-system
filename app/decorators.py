"""Authorization decorators for role-based access control."""
from functools import wraps
from flask import abort, flash, redirect, url_for
# pyrefly: ignore [missing-import]
from flask_login import current_user


def role_required(*roles):
    """Decorator that restricts access to users with specific roles.

    Usage:
        @role_required('admin')
        @role_required('admin', 'officer')

    Enforces server-side authorization — not merely a UI restriction.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login'))

            # Check if MFA verification is pending
            from flask import session
            if current_user.mfa_enabled and not session.get('mfa_verified'):
                flash('Please complete MFA verification.', 'warning')
                return redirect(url_for('auth.mfa_verify'))

            if current_user.role not in roles:
                # Log the unauthorized access attempt
                from .services.audit import log_event
                log_event(
                    user_id=current_user.id,
                    action='UNAUTHORIZED_ACCESS',
                    resource_type='route',
                    status='BLOCKED',
                    details=f'Role {current_user.role} attempted to access route requiring {roles}',
                )
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def login_and_mfa_required(f):
    """Decorator ensuring user is logged in AND has completed MFA if enabled."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))

        from flask import session
        if current_user.mfa_enabled and not session.get('mfa_verified'):
            flash('Please complete MFA verification.', 'warning')
            return redirect(url_for('auth.mfa_verify'))

        return f(*args, **kwargs)
    return decorated_function
