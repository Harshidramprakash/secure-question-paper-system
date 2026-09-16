"""Tests for Phase 4: Approvals and Multi-Party Assembly."""
import pytest
from datetime import datetime, timezone, date

from app.models.question_paper import QuestionPaper
from app.models.question_section import QuestionSection
from app.models.approval import Approval
from app.services.encryption import encrypt_content
from app.services.assembly import assemble_paper, AssemblyError
from tests.conftest import login

class TestAdminReviewWorkflow:
    @pytest.fixture
    def review_setup(self, db, admin_user, setter_a):
        """Create a submitted section ready for review."""
        paper = QuestionPaper(
            title="Review Paper",
            exam_date=date(2026, 12, 1),
            release_time=datetime(2026, 12, 1, 8, 0, tzinfo=timezone.utc),
            created_by=admin_user.id,
            status=QuestionPaper.STATUS_UNDER_REVIEW
        )
        db.session.add(paper)
        db.session.flush()

        plaintext = "Test question content"
        encrypted_content, nonce = encrypt_content(plaintext)
        # Using a dummy hash just for this test unless encryption hashing is integrated here
        from app.services.encryption import compute_hash
        content_hash = compute_hash(plaintext)

        sec1 = QuestionSection(
            paper_id=paper.id,
            setter_id=setter_a.id,
            section_name="Section 1",
            section_order=1,
            status=QuestionSection.STATUS_SUBMITTED,
            encrypted_content=encrypted_content,
            nonce=nonce,
            content_hash=content_hash,
            submitted_at=datetime.now(timezone.utc)
        )
        db.session.add(sec1)
        db.session.commit()
        return paper, sec1

    def test_admin_can_approve_section(self, client, admin_user, review_setup):
        """Admin can approve a submitted section."""
        paper, sec1 = review_setup
        login(client, admin_user.username, 'Admin@123')
        
        response = client.post(f'/admin/section/{sec1.id}/review', data={
            'action': 'approve',
            'comments': 'Looks good'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Section approved successfully' in response.data
        
        # Verify database changes
        sec1_db = QuestionSection.query.get(sec1.id)
        assert sec1_db.status == QuestionSection.STATUS_APPROVED
        assert sec1_db.approved_at is not None
        
        # Verify approval record
        approval = Approval.query.filter_by(section_id=sec1.id).first()
        assert approval is not None
        assert approval.action == Approval.ACTION_APPROVED
        assert approval.comments == 'Looks good'
        assert approval.approver_id == admin_user.id

    def test_admin_can_reject_section(self, client, admin_user, review_setup):
        """Admin can reject a submitted section with comments."""
        paper, sec1 = review_setup
        login(client, admin_user.username, 'Admin@123')
        
        response = client.post(f'/admin/section/{sec1.id}/review', data={
            'action': 'reject',
            'comments': 'Questions are too easy.'
        }, follow_redirects=True)
        
        assert b'Section rejected successfully' in response.data
        sec1_db = QuestionSection.query.get(sec1.id)
        assert sec1_db.status == QuestionSection.STATUS_REJECTED

    def test_rejection_requires_comments(self, client, admin_user, review_setup):
        """Admin cannot reject without providing comments."""
        paper, sec1 = review_setup
        login(client, admin_user.username, 'Admin@123')
        
        response = client.post(f'/admin/section/{sec1.id}/review', data={
            'action': 'reject',
            'comments': ''
        }, follow_redirects=True)
        
        assert b'Comments are required' in response.data
        assert QuestionSection.query.get(sec1.id).status == QuestionSection.STATUS_SUBMITTED

    def test_setter_cannot_approve_section(self, client, setter_a, review_setup):
        """Setter has no authorization to approve a section."""
        paper, sec1 = review_setup
        login(client, setter_a.username, 'SetterA@123')
        
        response = client.post(f'/admin/section/{sec1.id}/review', data={
            'action': 'approve',
            'comments': ''
        }, follow_redirects=True)
        
        assert response.status_code == 403
        assert QuestionSection.query.get(sec1.id).status == QuestionSection.STATUS_SUBMITTED


class TestMultiPartyAssembly:
    @pytest.fixture
    def assembly_setup(self, db, admin_user, setter_a, setter_b):
        """Create a paper with two approved sections ready for assembly."""
        paper = QuestionPaper(
            title="Assembly Paper",
            exam_date=date(2026, 12, 1),
            release_time=datetime(2026, 12, 1, 8, 0, tzinfo=timezone.utc),
            created_by=admin_user.id,
            status=QuestionPaper.STATUS_UNDER_REVIEW
        )
        db.session.add(paper)
        db.session.flush()

        from app.services.encryption import compute_hash

        # Section 1
        pt1 = "Section 1 Question"
        enc1, nonce1 = encrypt_content(pt1)
        sec1 = QuestionSection(
            paper_id=paper.id, setter_id=setter_a.id, section_name="Part A",
            section_order=1, status=QuestionSection.STATUS_APPROVED,
            encrypted_content=enc1, nonce=nonce1, content_hash=compute_hash(pt1)
        )
        
        # Section 2
        pt2 = "Section 2 Question"
        enc2, nonce2 = encrypt_content(pt2)
        sec2 = QuestionSection(
            paper_id=paper.id, setter_id=setter_b.id, section_name="Part B",
            section_order=2, status=QuestionSection.STATUS_APPROVED,
            encrypted_content=enc2, nonce=nonce2, content_hash=compute_hash(pt2)
        )

        db.session.add_all([sec1, sec2])
        db.session.commit()
        return paper, sec1, sec2

    def test_successful_assembly(self, app, assembly_setup):
        """Verify successful assembly with integrity checking and re-encryption."""
        paper, sec1, sec2 = assembly_setup
        
        with app.app_context():
            assembled_paper = assemble_paper(paper.id)
            
            assert assembled_paper.status == QuestionPaper.STATUS_READY_FOR_RELEASE
            assert assembled_paper.encrypted_content is not None
            assert assembled_paper.nonce is not None
            assert assembled_paper.content_hash is not None
            
            # Verify the decrypted content of the final assembled paper
            from app.services.encryption import decrypt_content
            final_text = decrypt_content(assembled_paper.encrypted_content, assembled_paper.nonce)
            assert "Part A" in final_text
            assert "Section 1 Question" in final_text
            assert "Part B" in final_text
            assert "Section 2 Question" in final_text

    def test_assembly_blocked_when_not_all_approved(self, app, assembly_setup):
        """Assembly must fail if a section is not approved."""
        paper, sec1, sec2 = assembly_setup
        
        with app.app_context():
            sec2.status = QuestionSection.STATUS_SUBMITTED
            from app.extensions import db
            db.session.commit()
            
            with pytest.raises(AssemblyError, match="not all sections are approved"):
                assemble_paper(paper.id)

    def test_assembly_blocked_on_integrity_failure(self, app, assembly_setup):
        """Assembly must fail if a section's hash does not match its decrypted plaintext."""
        paper, sec1, sec2 = assembly_setup
        
        with app.app_context():
            # Tamper with the hash (or plaintext)
            sec1.content_hash = "fakehash12345"
            from app.extensions import db
            db.session.commit()
            
            with pytest.raises(AssemblyError, match="Hash mismatch"):
                assemble_paper(paper.id)

    def test_assembly_route_unauthorized_access(self, client, setter_a, assembly_setup):
        """Setters cannot trigger assembly."""
        paper, sec1, sec2 = assembly_setup
        login(client, setter_a.username, 'SetterA@123')
        
        response = client.post(f'/admin/paper/{paper.id}/assemble')
        assert response.status_code == 403
        
        with client.application.app_context():
            p = QuestionPaper.query.get(paper.id)
            assert p.status == QuestionPaper.STATUS_UNDER_REVIEW

    def test_assembly_route_success(self, client, admin_user, assembly_setup):
        """Admin triggering assembly via POST route."""
        paper, sec1, sec2 = assembly_setup
        login(client, admin_user.username, 'Admin@123')
        
        response = client.post(f'/admin/paper/{paper.id}/assemble', follow_redirects=True)
        assert response.status_code == 200
        assert b'Paper successfully assembled and securely encrypted' in response.data
        
        with client.application.app_context():
            p = QuestionPaper.query.get(paper.id)
            assert p.status == QuestionPaper.STATUS_READY_FOR_RELEASE
