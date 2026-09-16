"""Examination Officer routes — handle secure time-locked release of papers."""
from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from ..decorators import role_required, login_and_mfa_required
from ..models.question_paper import QuestionPaper
from ..models.user import User
from ..services.audit import log_event
from ..services.release import authorize_release, get_decrypted_paper_content, ReleaseError

officer_bp = Blueprint('officer', __name__, url_prefix='/officer')


@officer_bp.route('/paper/<int:paper_id>/release', methods=['GET', 'POST'])
@login_required
@login_and_mfa_required
@role_required(User.ROLE_OFFICER)
def release_panel(paper_id):
    """Release authorization panel."""
    paper = QuestionPaper.query.get_or_404(paper_id)
    
    if paper.status == QuestionPaper.STATUS_RELEASED:
        return redirect(url_for('officer.exam_portal', paper_id=paper.id))
        
    if request.method == 'POST':
        try:
            authorize_release(paper.id, current_user.id)
            
            log_event(
                user_id=current_user.id,
                action='PAPER_RELEASE_AUTHORIZED',
                resource_type='paper',
                resource_id=paper.id,
                details=f'Paper "{paper.title}" release officially authorized.'
            )
            flash('Paper successfully released and decrypted for examination.', 'success')
            return redirect(url_for('officer.exam_portal', paper_id=paper.id))
            
        except ReleaseError as e:
            log_event(
                user_id=current_user.id,
                action='PAPER_RELEASE_FAILED',
                resource_type='paper',
                resource_id=paper.id,
                details=f'Release failed: {str(e)}'
            )
            flash(f'Release Failed: {str(e)}', 'error')

    # For GET requests, check if time is reached to display correct UI
    now = datetime.now(timezone.utc)
    release_time = paper.release_time
    if release_time and release_time.tzinfo is None:
        release_time = release_time.replace(tzinfo=timezone.utc)
        
    time_reached = now >= release_time if release_time else False
    
    return render_template('officer/release.html', paper=paper, time_reached=time_reached, now=now)


@officer_bp.route('/paper/<int:paper_id>/portal')
@login_required
@login_and_mfa_required
@role_required(User.ROLE_OFFICER)
def exam_portal(paper_id):
    """Secure examination portal for viewing the decrypted paper."""
    paper = QuestionPaper.query.get_or_404(paper_id)
    
    try:
        content = get_decrypted_paper_content(paper.id)
        
        log_event(
            user_id=current_user.id,
            action='PAPER_VIEWED_IN_PORTAL',
            resource_type='paper',
            resource_id=paper.id,
            details=f'Paper "{paper.title}" was viewed in the secure exam portal.'
        )
        return render_template('officer/exam_portal.html', paper=paper, content=content)
        
    except ReleaseError as e:
        flash(f'Cannot access exam portal: {str(e)}', 'error')
        return redirect(url_for('dashboard.index'))
