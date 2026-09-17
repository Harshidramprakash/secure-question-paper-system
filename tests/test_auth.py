"""Tests for authentication — login, logout, MFA, password hashing."""
import pyotp
from app.models.user import User
from app.models.audit_log import AuditLog
from tests.conftest import login


class TestPasswordHashing:
    """Verify password hashing never stores plaintext."""

    def test_password_is_hashed(self, db):
        """Password hash must differ from plaintext."""
        user = User(username='hashtest', role=User.ROLE_ADMIN)
        user.set_password('MySecret123')
        assert user.password_hash != 'MySecret123'
        assert user.password_hash.startswith('scrypt:')

    def test_correct_password_verifies(self, db):
        user = User(username='hashtest', role=User.ROLE_ADMIN)
        user.set_password('Correct@123')
        assert user.check_password('Correct@123') is True

    def test_wrong_password_fails(self, db):
        user = User(username='hashtest', role=User.ROLE_ADMIN)
        user.set_password('Correct@123')
        assert user.check_password('Wrong@456') is False


class TestLogin:
    """Test login success and failure scenarios."""

    def test_login_page_renders(self, client):
        """GET /auth/login should return 200."""
        resp = client.get('/auth/login')
        assert resp.status_code == 200
        assert b'Sign In' in resp.data

    def test_successful_login_no_mfa(self, client, admin_user):
        """Valid credentials (no MFA) should redirect to dashboard."""
        resp = login(client, 'admin', 'Admin@123')
        assert resp.status_code == 200
        assert b'Dashboard' in resp.data or b'Welcome' in resp.data

    def test_failed_login_wrong_password(self, client, admin_user):
        """Wrong password should show error."""
        resp = client.post('/auth/login', data={
            'username': 'admin',
            'password': 'WrongPassword',
        })
        assert resp.status_code == 401
        assert b'Invalid' in resp.data

    def test_failed_login_nonexistent_user(self, client):
        """Non-existent user should show error."""
        resp = client.post('/auth/login', data={
            'username': 'nobody',
            'password': 'anything',
        })
        assert resp.status_code == 401

    def test_inactive_user_blocked(self, client, db):
        """Deactivated users cannot log in."""
        user = User(username='inactive', role=User.ROLE_ADMIN, is_active=False)
        user.set_password('Test@123')
        db.session.add(user)
        db.session.commit()

        resp = client.post('/auth/login', data={
            'username': 'inactive',
            'password': 'Test@123',
        })
        assert resp.status_code == 403

    def test_login_audit_logged(self, client, admin_user):
        """Successful login should create an audit log entry."""
        login(client, 'admin', 'Admin@123')
        log = AuditLog.query.filter_by(action='LOGIN_SUCCESS').first()
        assert log is not None
        assert log.user_id == admin_user.id

    def test_failed_login_audit_logged(self, client, admin_user):
        """Failed login should create an audit log entry."""
        client.post('/auth/login', data={
            'username': 'admin',
            'password': 'wrong',
        })
        log = AuditLog.query.filter_by(action='LOGIN_FAILURE').first()
        assert log is not None


class TestMFA:
    """Test TOTP MFA flow."""

    def test_mfa_redirect_after_password(self, client, mfa_admin):
        """MFA-enabled user should be redirected to MFA page after correct password."""
        resp = client.post('/auth/login', data={
            'username': 'mfa_admin',
            'password': 'Admin@123',
        })
        # Should redirect to MFA verification
        assert resp.status_code == 302
        assert '/auth/mfa' in resp.headers.get('Location', '')

    def test_mfa_blocks_dashboard_access(self, client, mfa_admin):
        """MFA-pending user should not access dashboard."""
        # Login with correct password
        client.post('/auth/login', data={
            'username': 'mfa_admin',
            'password': 'Admin@123',
        })
        # Try to access dashboard — should redirect to MFA
        resp = client.get('/dashboard', follow_redirects=True)
        assert b'Verification Code' in resp.data or b'Two-Factor' in resp.data

    def test_mfa_correct_code_grants_access(self, client, mfa_admin):
        """Correct TOTP code should complete login."""
        # Login with password
        client.post('/auth/login', data={
            'username': 'mfa_admin',
            'password': 'Admin@123',
        })
        # Submit correct TOTP code
        totp = pyotp.TOTP(mfa_admin.mfa_secret)
        resp = client.post('/auth/mfa', data={
            'otp_code': totp.now(),
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b'Dashboard' in resp.data or b'Welcome' in resp.data

    def test_mfa_wrong_code_rejected(self, client, mfa_admin):
        """Wrong TOTP code should be rejected."""
        client.post('/auth/login', data={
            'username': 'mfa_admin',
            'password': 'Admin@123',
        })
        resp = client.post('/auth/mfa', data={
            'otp_code': '000000',
        })
        assert resp.status_code == 401

    def test_mfa_code_with_spaces_accepted(self, client, mfa_admin):
        """Valid TOTP code with spaces should be accepted (copy-paste resilience)."""
        client.post('/auth/login', data={
            'username': 'mfa_admin',
            'password': 'Admin@123',
        })
        totp = pyotp.TOTP(mfa_admin.mfa_secret)
        code = totp.now()
        # Add a space in the middle to simulate common user input formatting
        spaced_code = f"{code[:3]} {code[3:]}"
        resp = client.post('/auth/mfa', data={
            'otp_code': spaced_code,
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b'Dashboard' in resp.data or b'Welcome' in resp.data

    def test_mfa_invalid_totp_format_rejected(self, client, mfa_admin):
        """Non-numeric TOTP code should be rejected safely."""
        client.post('/auth/login', data={
            'username': 'mfa_admin',
            'password': 'Admin@123',
        })
        resp = client.post('/auth/mfa', data={
            'otp_code': 'ABC DEF',
        })
        assert resp.status_code == 400
        assert b'valid numeric verification code' in resp.data

    def test_mfa_audit_logged(self, client, mfa_admin):
        """MFA success and failure should be audit logged."""
        # Login
        client.post('/auth/login', data={
            'username': 'mfa_admin',
            'password': 'Admin@123',
        })
        # Submit wrong code
        client.post('/auth/mfa', data={'otp_code': '000000'})
        log = AuditLog.query.filter_by(action='MFA_FAILURE').first()
        assert log is not None

        # Submit correct code
        totp = pyotp.TOTP(mfa_admin.mfa_secret)
        client.post('/auth/mfa', data={'otp_code': totp.now()})
        log = AuditLog.query.filter_by(action='MFA_SUCCESS').first()
        assert log is not None


class TestLogout:
    """Test logout functionality."""

    def test_logout_redirects_to_login(self, client, admin_user):
        """Logout should redirect to the login page."""
        login(client, 'admin', 'Admin@123')
        resp = client.get('/auth/logout', follow_redirects=True)
        assert b'Sign In' in resp.data

    def test_logout_audit_logged(self, client, admin_user):
        """Logout should create an audit log entry."""
        login(client, 'admin', 'Admin@123')
        client.get('/auth/logout')
        log = AuditLog.query.filter_by(action='LOGOUT').first()
        assert log is not None


class TestDevAuthBypass:
    """Verify development-only MFA bypass behavior."""

    def test_bypass_disabled_by_default(self, mfa_admin):
        from app import create_app
        import os
        # Default testing environment config
        app = create_app('testing')
        assert app.config.get('DEV_AUTH_BYPASS') is False

    def test_bypass_fails_fast_in_production(self):
        """Production config should raise RuntimeError if bypass is enabled."""
        from app import create_app
        from app.config import ProductionConfig
        import pytest
        
        # We initialize with testing config to safely get an app instance
        app = create_app('testing')
        
        # Inject the unsafe bypass
        app.config['DEV_AUTH_BYPASS'] = True
        
        # Now explicitly run the production validation hook
        with pytest.raises(RuntimeError, match="DEV_AUTH_BYPASS must NEVER be enabled in production"):
            ProductionConfig.init_app(app)

    def test_bypass_works_only_in_development(self, client, mfa_admin, monkeypatch):
        """Test that the bypass succeeds when configured correctly."""
        from flask import session
        
        # We can simulate the dev environment on our test client app.
        client.application.config['DEV_AUTH_BYPASS'] = True
        client.application.config['DEBUG'] = True
        client.application.config['TESTING'] = False  # pretend to be dev

        resp = client.post('/auth/login', data={
            'username': 'mfa_admin',
            'password': 'Admin@123',
        }, follow_redirects=True)
        
        assert resp.status_code == 200
        assert b'Development MFA bypass active' in resp.data

        # Restore
        client.application.config['TESTING'] = True
        client.application.config['DEBUG'] = True
        client.application.config['DEV_AUTH_BYPASS'] = False
