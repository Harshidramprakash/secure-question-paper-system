"""Tests for Role-Based Access Control (RBAC)."""
from app.models.audit_log import AuditLog
from tests.conftest import login


class TestRBACDashboardAccess:
    """Verify each role sees only their authorized dashboard."""

    def test_setter_sees_setter_dashboard(self, client, setter_a):
        login(client, 'setter_a', 'SetterA@123')
        resp = client.get('/dashboard', follow_redirects=True)
        assert resp.status_code == 200
        assert b'My Assigned Sections' in resp.data

    def test_admin_sees_admin_dashboard(self, client, admin_user):
        login(client, 'admin', 'Admin@123')
        resp = client.get('/dashboard', follow_redirects=True)
        assert resp.status_code == 200
        assert b'Administration Dashboard' in resp.data

    def test_officer_sees_officer_dashboard(self, client, officer_user):
        login(client, 'officer', 'Officer@123')
        resp = client.get('/dashboard', follow_redirects=True)
        assert resp.status_code == 200
        assert b'Examination Officer Dashboard' in resp.data


class TestUnauthorizedAccess:
    """Verify that unauthenticated users are blocked."""

    def test_dashboard_requires_login(self, client):
        """Unauthenticated access to /dashboard should redirect to login."""
        resp = client.get('/dashboard')
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers.get('Location', '')

    def test_root_redirects_to_login(self, client):
        """Root / should redirect unauthenticated users to login."""
        resp = client.get('/')
        assert resp.status_code == 302


class TestCrossFunctionality:
    """Future-phase tests — these will be meaningful when setter/admin/officer routes exist."""

    def test_setter_cannot_access_root_without_auth(self, client):
        """Unauthenticated requests should be redirected."""
        resp = client.get('/dashboard')
        assert resp.status_code == 302
