"""Audit dashboard routes — securely view and monitor security events."""
from flask import Blueprint, render_template, request
# pyrefly: ignore [missing-import]
from flask_login import login_required

from ..decorators import role_required, login_and_mfa_required
from ..models.user import User
from ..models.audit_log import AuditLog
from ..extensions import db

audit_bp = Blueprint('audit', __name__, url_prefix='/audit')

@audit_bp.route('/logs')
@login_required
@login_and_mfa_required
@role_required(User.ROLE_ADMIN)
def logs():
    """View security audit logs (Admin only)."""
    page = request.args.get('page', 1, type=int)
    action_filter = request.args.get('action')
    status_filter = request.args.get('status')
    username_filter = request.args.get('username')
    
    query = AuditLog.query.order_by(AuditLog.created_at.desc())
    
    if action_filter:
        query = query.filter(AuditLog.action == action_filter)
    if status_filter:
        query = query.filter(AuditLog.status == status_filter)
    if username_filter:
        query = query.join(User).filter(User.username.ilike(f'%{username_filter}%'))
        
    pagination = query.paginate(page=page, per_page=20)
    
    # Pre-fetch stats
    total_events = AuditLog.query.count()
    failed_auth = AuditLog.query.filter(
        AuditLog.action.in_(['LOGIN_FAILED', 'MFA_FAILED']), 
        AuditLog.status == 'FAILURE'
    ).count()
    
    # Recent security events (e.g. failures, blocked access)
    recent_security_events = AuditLog.query.filter(
        (AuditLog.status == 'FAILURE') | (AuditLog.status == 'BLOCKED')
    ).order_by(AuditLog.created_at.desc()).limit(5).all()
    
    # Distinct actions and statuses for filters
    actions = [r[0] for r in db.session.query(AuditLog.action).distinct().all()]
    statuses = [r[0] for r in db.session.query(AuditLog.status).distinct().all()]
    
    return render_template('audit/logs.html', 
                          pagination=pagination,
                          total_events=total_events,
                          failed_auth=failed_auth,
                          recent_security_events=recent_security_events,
                          actions=actions,
                          statuses=statuses)
