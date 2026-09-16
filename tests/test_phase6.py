"""Tests for Phase 6: Audit Dashboard and Security Monitoring."""
from app.models.audit_log import AuditLog
from tests.conftest import login

class TestAuditDashboard:
    def test_admin_can_access_audit_dashboard(self, client, admin_user):
        """Admin can access the audit dashboard."""
        login(client, admin_user.username, 'Admin@123')
        response = client.get('/audit/logs')
        assert response.status_code == 200
        assert b'Security Audit Dashboard' in response.data

    def test_setter_cannot_access_audit_dashboard(self, client, setter_a):
        """Setter cannot access the audit dashboard."""
        login(client, setter_a.username, 'SetterA@123')
        response = client.get('/audit/logs')
        assert response.status_code == 403

    def test_officer_cannot_access_audit_dashboard(self, client, officer_user):
        """Officer cannot access the audit dashboard."""
        login(client, officer_user.username, 'Officer@123')
        response = client.get('/audit/logs')
        assert response.status_code == 403

    def test_audit_log_filtering(self, app, client, admin_user):
        """Audit logs can be filtered by action and status."""
        # Create some logs manually to test filtering
        with app.app_context():
            from app.services.audit import log_event
            log_event(admin_user.id, action='TEST_SUCCESS', status='SUCCESS', details='A successful test')
            log_event(admin_user.id, action='TEST_FAILURE', status='FAILURE', details='A failed test')

        login(client, admin_user.username, 'Admin@123')
        
        # Filter by action
        response = client.get('/audit/logs?action=TEST_FAILURE')
        assert b'A failed test' in response.data
        assert b'A successful test' not in response.data
        
        # Filter by status
        response = client.get('/audit/logs?status=SUCCESS')
        assert b'A successful test' in response.data
        assert b'A failed test' not in response.data

    def test_sensitive_data_exclusion(self, client, app):
        """Ensure passwords and secrets are not in audit logs (by checking the DB)."""
        with app.app_context():
            logs = AuditLog.query.all()
            for log in logs:
                if log.details:
                    assert 'Admin@123' not in log.details
                    assert 'SetterA@123' not in log.details
                    assert 'totp' not in log.details.lower()
                    assert 'secret' not in log.details.lower()

    def test_failed_login_is_audited(self, client, app):
        """Failed authentication attempts are logged."""
        client.post('/auth/login', data={'username': 'admin', 'password': 'wrongpassword'})
        
        with app.app_context():
            failed_log = AuditLog.query.filter_by(action='LOGIN_FAILURE').first()
            assert failed_log is not None
            assert failed_log.status == 'FAILURE'
            assert 'Failed login attempt' in failed_log.details
