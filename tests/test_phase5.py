"""Tests for Phase 5: Controlled Release and Examination Officer Portal."""
import pytest
from datetime import datetime, timezone, timedelta, date

from app.models.question_paper import QuestionPaper
from app.models.approval import Approval
from app.services.encryption import encrypt_content
from tests.conftest import login

class TestOfficerReleaseWorkflow:
    @pytest.fixture
    def release_setup(self, db, admin_user, officer_user):
        """Create an assembled paper ready for release."""
        # 1. Assembled Paper ready for release (time is in the past)
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        paper_ready = QuestionPaper(
            title="Ready Paper",
            exam_date=date.today(),
            release_time=past_time,
            created_by=admin_user.id,
            status=QuestionPaper.STATUS_READY_FOR_RELEASE
        )
        
        # 2. Assembled Paper NOT ready for release (time is in the future)
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        paper_future = QuestionPaper(
            title="Future Paper",
            exam_date=date.today(),
            release_time=future_time,
            created_by=admin_user.id,
            status=QuestionPaper.STATUS_READY_FOR_RELEASE
        )
        
        # 3. Unassembled Paper
        paper_unassembled = QuestionPaper(
            title="Unassembled Paper",
            exam_date=date.today(),
            release_time=past_time,
            created_by=admin_user.id,
            status=QuestionPaper.STATUS_APPROVED
        )

        db.session.add_all([paper_ready, paper_future, paper_unassembled])
        db.session.flush()
        
        # Encrypt some content for the ready paper so the portal can decrypt it
        pt = "Final Assembled Content"
        enc, nonce = encrypt_content(pt)
        paper_ready.encrypted_content = enc
        paper_ready.nonce = nonce
        
        paper_future.encrypted_content = enc
        paper_future.nonce = nonce
        
        db.session.commit()
        return paper_ready, paper_future, paper_unassembled

    def test_release_blocked_before_scheduled_time(self, client, officer_user, release_setup):
        paper_ready, paper_future, paper_unassembled = release_setup
        login(client, officer_user.username, 'Officer@123')
        
        response = client.post(f'/officer/paper/{paper_future.id}/release', follow_redirects=True)
        assert b'Cannot release paper before its scheduled release time' in response.data
        
        p = QuestionPaper.query.get(paper_future.id)
        assert p.status == QuestionPaper.STATUS_READY_FOR_RELEASE

    def test_release_blocked_when_assembly_incomplete(self, client, officer_user, release_setup):
        paper_ready, paper_future, paper_unassembled = release_setup
        login(client, officer_user.username, 'Officer@123')
        
        response = client.post(f'/officer/paper/{paper_unassembled.id}/release', follow_redirects=True)
        assert b'not fully assembled' in response.data
        
        p = QuestionPaper.query.get(paper_unassembled.id)
        assert p.status == QuestionPaper.STATUS_APPROVED

    def test_unauthorized_access_to_release(self, client, admin_user, setter_a, release_setup):
        paper_ready, paper_future, paper_unassembled = release_setup
        
        # Setter tries
        login(client, setter_a.username, 'SetterA@123')
        response = client.post(f'/officer/paper/{paper_ready.id}/release')
        assert response.status_code == 403
        
        # Admin tries
        login(client, admin_user.username, 'Admin@123')
        response = client.post(f'/officer/paper/{paper_ready.id}/release')
        assert response.status_code == 403

    def test_successful_authorized_release(self, client, officer_user, release_setup):
        paper_ready, paper_future, paper_unassembled = release_setup
        login(client, officer_user.username, 'Officer@123')
        
        response = client.post(f'/officer/paper/{paper_ready.id}/release', follow_redirects=True)
        assert b'Paper successfully released' in response.data
        
        p = QuestionPaper.query.get(paper_ready.id)
        assert p.status == QuestionPaper.STATUS_RELEASED
        
        # Verify approval log
        approval = Approval.query.filter_by(paper_id=p.id, action=Approval.ACTION_RELEASE_AUTHORIZED).first()
        assert approval is not None
        assert approval.approver_id == officer_user.id

    def test_duplicate_release_prevention(self, client, officer_user, release_setup):
        paper_ready, paper_future, paper_unassembled = release_setup
        login(client, officer_user.username, 'Officer@123')
        
        # First release
        client.post(f'/officer/paper/{paper_ready.id}/release', follow_redirects=True)
        
        # Second attempt (route handles it by redirecting, so no error is thrown in POST, but let's check GET)
        response = client.get(f'/officer/paper/{paper_ready.id}/release')
        assert response.status_code == 302
        assert '/officer/paper' in response.headers['Location']
        
        # If we bypass the route and use service directly
        from app.services.release import authorize_release, ReleaseError
        with pytest.raises(ReleaseError, match="already released"):
            with client.application.app_context():
                authorize_release(paper_ready.id, officer_user.id)

    def test_exam_portal_inaccessible_before_release(self, client, officer_user, release_setup):
        paper_ready, paper_future, paper_unassembled = release_setup
        login(client, officer_user.username, 'Officer@123')
        
        response = client.get(f'/officer/paper/{paper_ready.id}/portal', follow_redirects=True)
        assert b'has not been officially released' in response.data

    def test_exam_portal_accessible_after_valid_release(self, client, officer_user, release_setup):
        paper_ready, paper_future, paper_unassembled = release_setup
        login(client, officer_user.username, 'Officer@123')
        
        # Release it
        client.post(f'/officer/paper/{paper_ready.id}/release', follow_redirects=True)
        
        # View portal
        response = client.get(f'/officer/paper/{paper_ready.id}/portal')
        assert response.status_code == 200
        assert b'Final Assembled Content' in response.data
