"""Setter routes — view assigned sections and submit encrypted content."""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from ..extensions import db
from ..decorators import role_required, login_and_mfa_required
from ..models.question_section import QuestionSection
from ..models.user import User
from ..services.encryption import encrypt_content, compute_hash, EncryptionError
from ..services.audit import log_event

setter_bp = Blueprint('setter', __name__, url_prefix='/setter')


@setter_bp.route('/sections')
@login_required
@login_and_mfa_required
def sections():
    """List sections assigned to the current setter."""
    # This route is accessible by SETTER_A and SETTER_B
    if current_user.role not in [User.ROLE_SETTER_A, User.ROLE_SETTER_B]:
        flash('Unauthorized access.', 'error')
        return redirect(url_for('dashboard.index'))
        
    assigned_sections = QuestionSection.query.filter_by(setter_id=current_user.id).all()
    return render_template('setter/sections.html', sections=assigned_sections)


@setter_bp.route('/section/<int:section_id>', methods=['GET', 'POST'])
@login_required
@login_and_mfa_required
def section_detail(section_id):
    """View and submit a specific section."""
    if current_user.role not in [User.ROLE_SETTER_A, User.ROLE_SETTER_B]:
        flash('Unauthorized access.', 'error')
        return redirect(url_for('dashboard.index'))
        
    section = QuestionSection.query.get_or_404(section_id)
    
    # Enforce access control: setter can only access their own sections
    if section.setter_id != current_user.id:
        log_event(
            user_id=current_user.id,
            action='UNAUTHORIZED_ACCESS_ATTEMPT',
            resource_type='section',
            resource_id=section.id,
            status='DENIED',
            details=f'Setter {current_user.username} attempted to access section {section.id} assigned to another setter.'
        )
        flash('You are not authorized to access this section.', 'error')
        return redirect(url_for('setter.sections'))

    if request.method == 'POST':
        # Cannot modify if already submitted or approved
        if section.status in [QuestionSection.STATUS_SUBMITTED, QuestionSection.STATUS_APPROVED]:
            flash('This section has already been submitted and cannot be modified.', 'error')
            return redirect(url_for('setter.section_detail', section_id=section.id))
            
        content = request.form.get('content', '').strip()
        action = request.form.get('action') # 'save_draft' or 'submit'
        
        if not content:
            flash('Question content cannot be empty.', 'error')
            return render_template('setter/section_detail.html', section=section)
            
        try:
            # 1. Encrypt the content
            ciphertext, nonce = encrypt_content(content)
            
            # 2. Compute plaintext integrity hash
            content_hash = compute_hash(content)
            
            # 3. Store in database
            section.encrypted_content = ciphertext
            section.nonce = nonce
            section.content_hash = content_hash
            
            if action == 'submit':
                from datetime import datetime, timezone
                section.status = QuestionSection.STATUS_SUBMITTED
                section.submitted_at = datetime.now(timezone.utc)
                flash('Section submitted successfully for review.', 'success')
                log_event(
                    user_id=current_user.id,
                    action='SECTION_SUBMITTED',
                    resource_type='section',
                    resource_id=section.id,
                    details='Content encrypted and submitted for review.'
                )
            else:
                flash('Draft saved successfully.', 'success')
                log_event(
                    user_id=current_user.id,
                    action='SECTION_DRAFT_SAVED',
                    resource_type='section',
                    resource_id=section.id,
                    details='Content encrypted and saved as draft.'
                )
                
            db.session.commit()
            return redirect(url_for('setter.sections'))
            
        except EncryptionError as e:
            db.session.rollback()
            flash(f'Encryption failed: {str(e)}', 'error')
            log_event(
                user_id=current_user.id,
                action='ENCRYPTION_FAILED',
                resource_type='section',
                resource_id=section.id,
                status='FAILURE',
                details=str(e)
            )
        except Exception as e:
            db.session.rollback()
            flash('An unexpected error occurred while saving the section.', 'error')

    return render_template('setter/section_detail.html', section=section)
