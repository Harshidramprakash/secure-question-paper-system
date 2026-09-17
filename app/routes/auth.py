"""Authentication routes — login, logout, MFA verification."""
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
# pyrefly: ignore [missing-import]
from flask_login import login_user, logout_user, current_user, login_required
# pyrefly: ignore [missing-import]
import pyotp

from ..extensions import db
from ..models.user import User
from ..services.audit import log_event

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login with password and optional MFA."""
    if current_user.is_authenticated and session.get('mfa_verified', True):
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Please enter both username and password.', 'error')
            return render_template('auth/login.html'), 400

        user = User.query.filter_by(username=username).first()

        # Check credentials
        if user is None or not user.check_password(password):
            log_event(
                user_id=user.id if user else None,
                action='LOGIN_FAILURE',
                resource_type='user',
                resource_id=user.id if user else None,
                status='FAILURE',
                details=f'Failed login attempt for username: {username}',
            )
            flash('Invalid username or password.', 'error')
            return render_template('auth/login.html'), 401

        # Check if account is active
        if not user.is_active:
            log_event(
                user_id=user.id,
                action='LOGIN_FAILURE',
                resource_type='user',
                resource_id=user.id,
                status='BLOCKED',
                details='Inactive account login attempt',
            )
            flash('Your account has been deactivated. Contact the administrator.', 'error')
            return render_template('auth/login.html'), 403

        # Password is correct — log the user in
        login_user(user)

        from flask import current_app
        is_dev = current_app.config.get('DEBUG') and not current_app.config.get('TESTING')

        # Development MFA bypass
        if current_app.config.get('DEV_AUTH_BYPASS') and is_dev:
            session['mfa_verified'] = True
            log_event(
                user_id=user.id,
                action='LOGIN_SUCCESS',
                resource_type='user',
                resource_id=user.id,
                status='SUCCESS',
                details='Login with Development MFA Bypass',
            )
            flash(f'Welcome, {user.username}! (Development MFA bypass active)', 'warning')
            return redirect(url_for('dashboard.index'))

        # If MFA is enabled, redirect to MFA verification (do NOT grant full access yet)
        if user.mfa_enabled:
            session['mfa_verified'] = False
            log_event(
                user_id=user.id,
                action='LOGIN_PASSWORD_OK',
                resource_type='user',
                resource_id=user.id,
                status='SUCCESS',
                details='Password verified, MFA pending',
            )
            return redirect(url_for('auth.mfa_verify'))

        # MFA not enabled — grant full access
        session['mfa_verified'] = True
        log_event(
            user_id=user.id,
            action='LOGIN_SUCCESS',
            resource_type='user',
            resource_id=user.id,
            status='SUCCESS',
            details='Login without MFA',
        )
        flash(f'Welcome, {user.username}!', 'success')
        return redirect(url_for('dashboard.index'))

    return render_template('auth/login.html')


@auth_bp.route('/mfa', methods=['GET', 'POST'])
@login_required
def mfa_verify():
    """Verify TOTP code after successful password login."""
    # If MFA is not enabled or already verified, redirect
    if not current_user.mfa_enabled or session.get('mfa_verified'):
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        otp_code = request.form.get('otp_code', '').replace(' ', '').strip()

        if not otp_code or not otp_code.isdigit():
            flash('Please enter a valid numeric verification code.', 'error')
            return render_template('auth/mfa_verify.html'), 400

        # Verify the TOTP code
        totp = pyotp.TOTP(current_user.mfa_secret)
        if totp.verify(otp_code, valid_window=1):
            session['mfa_verified'] = True
            log_event(
                user_id=current_user.id,
                action='MFA_SUCCESS',
                resource_type='user',
                resource_id=current_user.id,
                status='SUCCESS',
                details='TOTP verification successful',
            )
            flash(f'Welcome, {current_user.username}!', 'success')
            return redirect(url_for('dashboard.index'))
        else:
            log_event(
                user_id=current_user.id,
                action='MFA_FAILURE',
                resource_type='user',
                resource_id=current_user.id,
                status='FAILURE',
                details='Invalid TOTP code',
            )
            flash('Invalid verification code. Please try again.', 'error')
            return render_template('auth/mfa_verify.html'), 401

    return render_template('auth/mfa_verify.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """Log out the current user and clear the session."""
    user_id = current_user.id
    username = current_user.username
    log_event(
        user_id=user_id,
        action='LOGOUT',
        resource_type='user',
        resource_id=user_id,
        status='SUCCESS',
        details=f'User {username} logged out',
    )
    session.pop('mfa_verified', None)
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
