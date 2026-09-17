"""Dashboard routes — role-based landing pages."""
from flask import Blueprint, render_template, redirect, url_for
# pyrefly: ignore [missing-import]
from flask_login import login_required, current_user

from ..decorators import role_required, login_and_mfa_required
from ..models.user import User

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
def index():
    """Root route — redirect to login or role-appropriate dashboard."""
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    return redirect(url_for('dashboard.home'))


@dashboard_bp.route('/dashboard')
@login_required
@login_and_mfa_required
def home():
    """Dispatch to the correct role-based dashboard."""
    if current_user.role in (User.ROLE_SETTER_A, User.ROLE_SETTER_B):
        return _setter_dashboard()
    elif current_user.role == User.ROLE_ADMIN:
        return _admin_dashboard()
    elif current_user.role == User.ROLE_OFFICER:
        return _officer_dashboard()
    else:
        return redirect(url_for('auth.login'))


def _setter_dashboard():
    """Dashboard for question setters — shows their assigned sections."""
    from ..models.question_section import QuestionSection
    sections = QuestionSection.query.filter_by(
        setter_id=current_user.id
    ).order_by(QuestionSection.id.desc()).all()
    return render_template('dashboard/setter.html', sections=sections)


def _admin_dashboard():
    """Dashboard for administrators — shows papers and pending reviews."""
    from ..models.question_paper import QuestionPaper
    from ..models.question_section import QuestionSection
    papers = QuestionPaper.query.order_by(QuestionPaper.created_at.desc()).all()
    pending_sections = QuestionSection.query.filter_by(
        status=QuestionSection.STATUS_SUBMITTED
    ).order_by(QuestionSection.submitted_at.desc()).all()
    return render_template(
        'dashboard/admin.html',
        papers=papers,
        pending_sections=pending_sections,
    )


def _officer_dashboard():
    """Dashboard for examination officers — shows papers ready for release."""
    from ..models.question_paper import QuestionPaper
    papers = QuestionPaper.query.filter(
        QuestionPaper.status.in_([
            QuestionPaper.STATUS_APPROVED,
            QuestionPaper.STATUS_READY_FOR_RELEASE,
            QuestionPaper.STATUS_RELEASED,
        ])
    ).order_by(QuestionPaper.release_time.desc()).all()
    return render_template('dashboard/officer.html', papers=papers)
