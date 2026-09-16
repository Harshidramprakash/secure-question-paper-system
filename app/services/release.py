"""Release service for authorizing and decrypting assembled papers."""
from datetime import datetime, timezone
from app.extensions import db
from app.models.question_paper import QuestionPaper
from app.models.approval import Approval
from app.services.encryption import decrypt_content, EncryptionError


class ReleaseError(Exception):
    """Raised when release fails due to validation or timing issues."""
    pass


def authorize_release(paper_id, approver_id):
    """
    Authorize the release of a paper.
    
    Conditions:
    1. Paper must be in READY_FOR_RELEASE state (assembled).
    2. Current time must be >= scheduled release_time.
    3. Cannot be released twice.
    
    Returns the updated QuestionPaper object.
    Raises ReleaseError on failure.
    """
    paper = QuestionPaper.query.get(paper_id)
    if not paper:
        raise ReleaseError(f"Paper {paper_id} not found.")

    if paper.status == QuestionPaper.STATUS_RELEASED:
        raise ReleaseError("Paper is already released.")

    if paper.status != QuestionPaper.STATUS_READY_FOR_RELEASE:
        raise ReleaseError("Paper is not fully assembled and ready for release.")

    now = datetime.now(timezone.utc)
    release_time = paper.release_time
    if release_time.tzinfo is None:
        release_time = release_time.replace(tzinfo=timezone.utc)
        
    if now < release_time:
        raise ReleaseError("Cannot release paper before its scheduled release time.")

    # Record release authorization
    approval = Approval(
        paper_id=paper.id,
        approver_id=approver_id,
        action=Approval.ACTION_RELEASE_AUTHORIZED,
        comments="Authorized by Examination Officer via secure portal."
    )
    db.session.add(approval)
    
    paper.status = QuestionPaper.STATUS_RELEASED
    db.session.commit()
    
    return paper


def get_decrypted_paper_content(paper_id):
    """
    Decrypts and returns the full assembled question paper plaintext.
    
    This function should ONLY be called when the paper is successfully RELEASED.
    It performs the final decryption entirely in memory.
    """
    paper = QuestionPaper.query.get(paper_id)
    if not paper:
        raise ReleaseError(f"Paper {paper_id} not found.")

    if paper.status != QuestionPaper.STATUS_RELEASED:
        raise ReleaseError("Cannot view paper: it has not been officially released.")

    if not paper.encrypted_content or not paper.nonce:
        raise ReleaseError("Paper content is missing cryptographic data.")

    try:
        plaintext = decrypt_content(paper.encrypted_content, paper.nonce)
        return plaintext
    except EncryptionError:
        raise ReleaseError("Integrity check failed during final decryption. Paper may be tampered with.")
