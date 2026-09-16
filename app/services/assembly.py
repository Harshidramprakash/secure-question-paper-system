"""Assembly service for generating the full question paper."""
from app.extensions import db
from app.models.question_paper import QuestionPaper
from app.models.question_section import QuestionSection
from app.services.encryption import encrypt_content, decrypt_content, verify_integrity, compute_hash, EncryptionError


class AssemblyError(Exception):
    """Raised when assembly fails due to validation or integrity issues."""
    pass


def assemble_paper(paper_id):
    """
    Assemble the complete question paper from its approved sections.
    
    1. Verifies all sections are approved.
    2. Verifies cryptographic integrity of every section.
    3. Decrypts sections in memory.
    4. Concatenates in order.
    5. Encrypts the final assembled paper.
    6. Stores the encrypted assembled paper and updates status.
    
    Returns the updated QuestionPaper object.
    Raises AssemblyError on failure.
    """
    paper = QuestionPaper.query.get(paper_id)
    if not paper:
        raise AssemblyError(f"Paper {paper_id} not found.")

    if paper.status in (QuestionPaper.STATUS_READY_FOR_RELEASE, QuestionPaper.STATUS_RELEASED):
        raise AssemblyError("Paper is already assembled.")

    if not paper.all_sections_approved:
        raise AssemblyError("Cannot assemble paper: not all sections are approved.")

    sections = paper.sections.order_by(QuestionSection.section_order).all()
    if not sections:
        raise AssemblyError("Paper has no sections.")

    assembled_parts = []
    
    for section in sections:
        if not section.encrypted_content or not section.nonce or not section.content_hash:
            raise AssemblyError(f"Section '{section.section_name}' is missing cryptographic data.")
            
        try:
            # Decrypt section
            plaintext = decrypt_content(section.encrypted_content, section.nonce)
        except EncryptionError:
            raise AssemblyError(f"Integrity check failed for section '{section.section_name}' during decryption.")
            
        # Verify hash
        if not verify_integrity(plaintext, section.content_hash):
            raise AssemblyError(f"Hash mismatch for section '{section.section_name}'. Possible tampering.")
            
        # Format the section for the final paper
        part = f"--- {section.section_name} ---\n{plaintext}\n"
        assembled_parts.append(part)
        
    # Combine all parts
    full_plaintext = "\n".join(assembled_parts)
    
    # Encrypt the final paper
    try:
        final_ciphertext, final_nonce = encrypt_content(full_plaintext)
        final_hash = compute_hash(full_plaintext)
    except Exception as e:
        raise AssemblyError(f"Failed to encrypt assembled paper: {str(e)}")
        
    # Store in database
    paper.encrypted_content = final_ciphertext
    paper.nonce = final_nonce
    paper.content_hash = final_hash
    paper.status = QuestionPaper.STATUS_READY_FOR_RELEASE
    
    db.session.commit()
    
    return paper
