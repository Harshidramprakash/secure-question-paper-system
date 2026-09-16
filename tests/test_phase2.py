"""Tests for Phase 2 and Encryption Service."""
import pytest
from datetime import datetime, timezone, date

from app.models.question_paper import QuestionPaper
from app.models.question_section import QuestionSection
from app.services.encryption import encrypt_content, decrypt_content, compute_hash, verify_integrity, EncryptionError
from tests.conftest import login


class TestEncryptionService:
    def test_encrypt_decrypt_success(self, app):
        """Test symmetric encryption and decryption."""
        with app.app_context():
            plaintext = "What is the time complexity of QuickSort?"
            ciphertext, nonce = encrypt_content(plaintext)
            
            assert ciphertext != plaintext.encode('utf-8')
            
            decrypted = decrypt_content(ciphertext, nonce)
            assert decrypted == plaintext
            
    def test_encryption_fails_with_tampering(self, app):
        """Test that modifying ciphertext raises EncryptionError (GCM authentication check)."""
        with app.app_context():
            plaintext = "Secret question."
            ciphertext, nonce = encrypt_content(plaintext)
            
            # Tamper with the ciphertext (flip a byte)
            tampered_ciphertext = bytearray(ciphertext)
            tampered_ciphertext[0] = tampered_ciphertext[0] ^ 0xFF
            
            with pytest.raises(EncryptionError):
                decrypt_content(bytes(tampered_ciphertext), nonce)
                
    def test_hashing(self, app):
        """Test SHA-256 hashing."""
        with app.app_context():
            plaintext = "Hash this."
            digest = compute_hash(plaintext)
            
            assert verify_integrity(plaintext, digest) is True
            assert verify_integrity("Tampered text", digest) is False


class TestAdminPaperManagement:
    def test_admin_can_create_paper(self, client, admin_user, setter_a, setter_b):
        """Admin can create a paper and assign sections."""
        login(client, admin_user.username, 'Admin@123')
        
        # Post the creation form
        response = client.post('/admin/paper/create', data={
            'title': 'Test Paper 2026',
            'description': 'Test description',
            'exam_date': '2026-12-01',
            'release_time': '2026-12-01T08:00',
            'section1_name': 'Section A',
            'section1_setter': setter_a.id,
            'section2_name': 'Section B',
            'section2_setter': setter_b.id
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Question paper created and sections assigned successfully' in response.data
        
        # Verify database state
        paper = QuestionPaper.query.filter_by(title='Test Paper 2026').first()
        assert paper is not None
        assert paper.status == QuestionPaper.STATUS_SECTIONS_ASSIGNED
        assert paper.exam_date == date(2026, 12, 1)
        
        sections = QuestionSection.query.filter_by(paper_id=paper.id).order_by(QuestionSection.section_order).all()
        assert len(sections) == 2
        assert sections[0].setter_id == setter_a.id
        assert sections[1].setter_id == setter_b.id
        assert sections[0].status == QuestionSection.STATUS_PENDING
        
    def test_cannot_assign_same_setter_to_both_sections(self, client, admin_user, setter_a):
        """Enforce multi-party constraint."""
        login(client, admin_user.username, 'Admin@123')
        
        response = client.post('/admin/paper/create', data={
            'title': 'Invalid Paper',
            'exam_date': '2026-12-01',
            'release_time': '2026-12-01T08:00',
            'section1_name': 'Section A',
            'section1_setter': setter_a.id,
            'section2_name': 'Section B',
            'section2_setter': setter_a.id  # Same setter
        }, follow_redirects=True)
        
        assert b'Different setters must be assigned' in response.data
        paper = QuestionPaper.query.filter_by(title='Invalid Paper').first()
        assert paper is None


class TestSetterSectionManagement:
    @pytest.fixture
    def setup_paper(self, db, admin_user, setter_a, setter_b):
        """Create a paper for testing setter flows."""
        paper = QuestionPaper(
            title="Setup Paper",
            exam_date=date(2026, 12, 1),
            release_time=datetime(2026, 12, 1, 8, 0, tzinfo=timezone.utc),
            created_by=admin_user.id,
            status=QuestionPaper.STATUS_SECTIONS_ASSIGNED
        )
        db.session.add(paper)
        db.session.flush()
        
        sec1 = QuestionSection(
            paper_id=paper.id, setter_id=setter_a.id,
            section_name="Part 1", section_order=1, status=QuestionSection.STATUS_PENDING
        )
        sec2 = QuestionSection(
            paper_id=paper.id, setter_id=setter_b.id,
            section_name="Part 2", section_order=2, status=QuestionSection.STATUS_PENDING
        )
        db.session.add_all([sec1, sec2])
        db.session.commit()
        return paper, sec1, sec2

    def test_setter_sees_assigned_sections(self, client, setter_a, setup_paper):
        """Setter should only see their assigned section."""
        paper, sec1, sec2 = setup_paper
        login(client, setter_a.username, 'SetterA@123')
        
        response = client.get('/setter/sections')
        assert response.status_code == 200
        assert b'Part 1' in response.data
        assert b'Part 2' not in response.data

    def test_setter_cannot_access_unassigned_section(self, client, setter_a, setup_paper):
        """Setter A cannot view Setter B's section."""
        paper, sec1, sec2 = setup_paper
        login(client, setter_a.username, 'SetterA@123')
        
        # Try to access sec2 (assigned to setter_b)
        response = client.get(f'/setter/section/{sec2.id}', follow_redirects=True)
        assert b'You are not authorized to access this section' in response.data

    def test_setter_submit_section_encrypts_content(self, client, setter_a, setup_paper):
        """Submitting a section encrypts it and updates status."""
        paper, sec1, sec2 = setup_paper
        login(client, setter_a.username, 'SetterA@123')
        
        plaintext = "This is a secret exam question."
        
        response = client.post(f'/setter/section/{sec1.id}', data={
            'content': plaintext,
            'action': 'submit'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Section submitted successfully for review.' in response.data
        
        # Check database
        sec1_db = QuestionSection.query.get(sec1.id)
        assert sec1_db.status == QuestionSection.STATUS_SUBMITTED
        assert sec1_db.encrypted_content is not None
        assert sec1_db.nonce is not None
        assert sec1_db.content_hash is not None
        
        # Verify plaintext is not stored directly anywhere (it's encrypted)
        decrypted = decrypt_content(sec1_db.encrypted_content, sec1_db.nonce)
        assert decrypted == plaintext
