"""Admin routes — manage papers, sections, and assignments."""
from datetime import datetime, timezone, time
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from ..extensions import db
from ..decorators import role_required, login_and_mfa_required
from ..models.question_paper import QuestionPaper
from ..models.question_section import QuestionSection
from ..models.user import User
from ..models.approval import Approval
from ..services.encryption import decrypt_content, EncryptionError
from ..services.audit import log_event
from ..services.assembly import assemble_paper, AssemblyError

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/papers')
@login_required
@login_and_mfa_required
@role_required(User.ROLE_ADMIN)
def papers():
    """List all question papers."""
    papers_list = QuestionPaper.query.order_by(QuestionPaper.created_at.desc()).all()
    return render_template('admin/papers.html', papers=papers_list)


@admin_bp.route('/paper/create', methods=['GET', 'POST'])
@login_required
@login_and_mfa_required
@role_required(User.ROLE_ADMIN)
def create_paper():
    """Create a new question paper and define its sections."""
    # Get all active setters for the assignment dropdowns
    setters = User.query.filter(User.role.in_([User.ROLE_SETTER_A, User.ROLE_SETTER_B]), User.is_active == True).all()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        exam_date_str = request.form.get('exam_date', '').strip()
        release_time_str = request.form.get('release_time', '').strip()
        
        # Section data
        section1_name = request.form.get('section1_name', '').strip()
        section1_setter = request.form.get('section1_setter')
        section2_name = request.form.get('section2_name', '').strip()
        section2_setter = request.form.get('section2_setter')

        if not title or not exam_date_str or not release_time_str or not section1_name or not section2_name:
            flash('Please fill in all required fields.', 'error')
            return render_template('admin/create_paper.html', setters=setters)
            
        if not section1_setter or not section2_setter:
            flash('Please assign setters to all sections.', 'error')
            return render_template('admin/create_paper.html', setters=setters)

        if section1_setter == section2_setter:
            flash('Different setters must be assigned to different sections to maintain multi-party security.', 'error')
            return render_template('admin/create_paper.html', setters=setters)

        try:
            # Parse dates (assuming HTML5 date and time-local inputs)
            exam_date = datetime.strptime(exam_date_str, '%Y-%m-%d').date()
            # Release time comes from a datetime-local input, we treat it as UTC for simplicity in this prototype
            # In a production system, we'd handle timezones properly with APP_TIMEZONE
            release_dt_naive = datetime.strptime(release_time_str, '%Y-%m-%dT%H:%M')
            release_dt_aware = release_dt_naive.replace(tzinfo=timezone.utc)
            
            # Create the paper
            paper = QuestionPaper(
                title=title,
                description=description,
                exam_date=exam_date,
                release_time=release_dt_aware,
                created_by=current_user.id,
                status=QuestionPaper.STATUS_SECTIONS_ASSIGNED
            )
            db.session.add(paper)
            db.session.flush() # Get paper ID
            
            # Create Section 1
            sec1 = QuestionSection(
                paper_id=paper.id,
                setter_id=int(section1_setter),
                section_name=section1_name,
                section_order=1,
                status=QuestionSection.STATUS_PENDING
            )
            
            # Create Section 2
            sec2 = QuestionSection(
                paper_id=paper.id,
                setter_id=int(section2_setter),
                section_name=section2_name,
                section_order=2,
                status=QuestionSection.STATUS_PENDING
            )
            
            db.session.add(sec1)
            db.session.add(sec2)
            db.session.commit()
            
            log_event(
                user_id=current_user.id,
                action='PAPER_CREATED',
                resource_type='paper',
                resource_id=paper.id,
                details=f'Paper "{title}" created with 2 sections assigned.'
            )
            
            flash('Question paper created and sections assigned successfully.', 'success')
            return redirect(url_for('admin.papers'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating paper: {str(e)}', 'error')

    return render_template('admin/create_paper.html', setters=setters)


@admin_bp.route('/paper/<int:paper_id>')
@login_required
@login_and_mfa_required
@role_required(User.ROLE_ADMIN)
def paper_detail(paper_id):
    """View details of a specific paper."""
    paper = QuestionPaper.query.get_or_404(paper_id)
    return render_template('admin/paper_detail.html', paper=paper)


@admin_bp.route('/section/<int:section_id>/review', methods=['GET', 'POST'])
@login_required
@login_and_mfa_required
@role_required(User.ROLE_ADMIN)
def review_section(section_id):
    """Review a submitted section and approve/reject it."""
    section = QuestionSection.query.get_or_404(section_id)
    
    if section.status not in (QuestionSection.STATUS_SUBMITTED, QuestionSection.STATUS_APPROVED, QuestionSection.STATUS_REJECTED):
        flash('This section is not ready for review.', 'warning')
        return redirect(url_for('admin.paper_detail', paper_id=section.paper_id))

    decrypted_content = None
    if section.encrypted_content and section.nonce:
        try:
            decrypted_content = decrypt_content(section.encrypted_content, section.nonce)
        except EncryptionError:
            flash('Error decrypting section. The content may have been tampered with or is corrupted.', 'error')
            decrypted_content = "ERROR: Decryption Failed."

    if request.method == 'POST':
        action = request.form.get('action')
        comments = request.form.get('comments', '').strip()

        if action not in ('approve', 'reject'):
            flash('Invalid action.', 'error')
            return redirect(url_for('admin.review_section', section_id=section_id))

        if action == 'reject' and not comments:
            flash('Comments are required when rejecting a section.', 'error')
            return render_template('admin/review_section.html', section=section, content=decrypted_content)

        new_status = QuestionSection.STATUS_APPROVED if action == 'approve' else QuestionSection.STATUS_REJECTED
        approval_action = Approval.ACTION_APPROVED if action == 'approve' else Approval.ACTION_REJECTED

        # Record approval
        approval = Approval(
            paper_id=section.paper_id,
            section_id=section.id,
            approver_id=current_user.id,
            action=approval_action,
            comments=comments
        )
        db.session.add(approval)
        
        # Update section status
        section.status = new_status
        if new_status == QuestionSection.STATUS_APPROVED:
            section.approved_at = datetime.now(timezone.utc)
            
        db.session.commit()

        log_event(
            user_id=current_user.id,
            action=f'SECTION_{approval_action}',
            resource_type='section',
            resource_id=section.id,
            details=f'Section "{section.section_name}" {new_status.lower()}.'
        )

        flash(f'Section {new_status.lower()} successfully.', 'success')
        return redirect(url_for('admin.paper_detail', paper_id=section.paper_id))

    return render_template('admin/review_section.html', section=section, content=decrypted_content)


@admin_bp.route('/paper/<int:paper_id>/assemble', methods=['POST'])
@login_required
@login_and_mfa_required
@role_required(User.ROLE_ADMIN)
def trigger_assembly(paper_id):
    """Trigger the Secure Multi-Party Assembly process."""
    from ..services.assembly import assemble_paper, AssemblyError
    try:
        paper = assemble_paper(paper_id)
        
        log_event(
            user_id=current_user.id,
            action='PAPER_ASSEMBLED',
            resource_type='paper',
            resource_id=paper.id,
            details=f'Paper "{paper.title}" successfully assembled.'
        )
        flash('Paper successfully assembled and securely encrypted.', 'success')
        
    except AssemblyError as e:
        log_event(
            user_id=current_user.id,
            action='PAPER_ASSEMBLY_FAILED',
            resource_type='paper',
            resource_id=paper_id,
            details=f'Assembly failed: {str(e)}'
        )
        flash(f'Assembly Failed: {str(e)}', 'error')
        
    return redirect(url_for('admin.paper_detail', paper_id=paper_id))


@admin_bp.route('/user/<int:user_id>/regenerate_mfa', methods=['GET', 'POST'])
@login_required
@login_and_mfa_required
@role_required(User.ROLE_ADMIN)
def regenerate_mfa(user_id):
    """Regenerate MFA secret and recovery codes for a user."""
    target_user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        admin_password = request.form.get('admin_password', '')
        
        if not admin_password or not current_user.check_password(admin_password):
            flash('Incorrect admin password. Authorization failed.', 'error')
            log_event(
                user_id=current_user.id,
                action='ADMIN_MFA_REGEN_FAILURE',
                resource_type='user',
                resource_id=target_user.id,
                status='FAILURE',
                details='Failed admin password verification during MFA regeneration'
            )
            return render_template('admin/regenerate_mfa.html', target_user=target_user), 401
            
        import pyotp
        from ..services.mfa import generate_mfa_qr_b64, generate_recovery_codes
        
        # Invalidate old secret and create a new one
        new_secret = pyotp.random_base32()
        target_user.mfa_secret = new_secret
        target_user.mfa_enabled = True
        
        # Generate new recovery codes
        new_recovery_codes = generate_recovery_codes(target_user.id)
        db.session.commit()
        
        qr_b64 = generate_mfa_qr_b64(target_user, new_secret)
        
        log_event(
            user_id=current_user.id,
            action='ADMIN_MFA_REGEN_SUCCESS',
            resource_type='user',
            resource_id=target_user.id,
            status='SUCCESS',
            details=f'MFA secret and recovery codes regenerated for {target_user.username}'
        )
        
        return render_template('admin/mfa_regenerated.html', target_user=target_user, qr_b64=qr_b64, recovery_codes=new_recovery_codes)
        
    return render_template('admin/regenerate_mfa.html', target_user=target_user)
