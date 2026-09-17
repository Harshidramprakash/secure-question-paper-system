"""Tests for MFA specific workflows (viewing, regenerating, recovery codes)."""
import pytest
import pyotp
from app.models.user import User
from app.models.recovery_code import RecoveryCode
from app.services.mfa import generate_recovery_codes
from tests.conftest import login

def test_mfa_view_requires_password(client, mfa_admin):
    """MFA view page requires password confirmation."""
    login(client, 'mfa_admin', 'Admin@123')
    
    # Needs a valid TOTP to fully login
    totp = pyotp.TOTP(mfa_admin.mfa_secret)
    client.post('/auth/mfa', data={'otp_code': totp.now()})
    
    # GET shows the form
    resp = client.get('/auth/mfa/view')
    assert resp.status_code == 200
    assert b're-enter your password' in resp.data
    
    # POST wrong password fails
    resp = client.post('/auth/mfa/view', data={'password': 'wrong'})
    assert b'Incorrect password' in resp.data
    
    # POST right password shows QR code
    resp = client.post('/auth/mfa/view', data={'password': 'Admin@123'})
    assert b'data:image/png;base64' in resp.data
    assert b'Your MFA QR Code' in resp.data

def test_recovery_code_verification_and_invalidation(client, mfa_admin, db):
    """Recovery code should log user in and be deleted afterwards."""
    # Generate recovery codes for user
    with client.application.app_context():
        codes = generate_recovery_codes(mfa_admin.id, count=2)
        code_to_use = codes[0]
        assert RecoveryCode.query.filter_by(user_id=mfa_admin.id).count() == 2
        
    client.post('/auth/login', data={
        'username': 'mfa_admin',
        'password': 'Admin@123',
    })
    
    # Submit recovery code
    resp = client.post('/auth/mfa', data={'otp_code': code_to_use}, follow_redirects=True)
    assert resp.status_code == 200
    assert b'recovery code was consumed' in resp.data
    
    # Check it was deleted
    with client.application.app_context():
        assert RecoveryCode.query.filter_by(user_id=mfa_admin.id).count() == 1

def test_admin_regenerate_mfa_success(client, admin_user, db):
    """Admin can regenerate MFA for another user."""
    # Create target user
    with client.application.app_context():
        target = User(username='target_user', role=User.ROLE_SETTER_A)
        target.set_password('Target@123')
        target.mfa_enabled = True
        target.mfa_secret = 'OLDSECRET'
        db.session.add(target)
        db.session.commit()
        target_id = target.id
    
    login(client, 'admin', 'Admin@123')
    
    # GET form
    resp = client.get(f'/admin/user/{target_id}/regenerate_mfa')
    assert resp.status_code == 200
    
    # POST right admin password
    resp = client.post(f'/admin/user/{target_id}/regenerate_mfa', data={
        'admin_password': 'Admin@123'
    })
    assert resp.status_code == 200
    assert b'MFA Successfully Regenerated' in resp.data
    assert b'New Recovery Codes' in resp.data
    
    # Verify DB was updated
    with client.application.app_context():
        updated_target = User.query.get(target_id)
        assert updated_target.mfa_secret != 'OLDSECRET'
        assert RecoveryCode.query.filter_by(user_id=target_id).count() == 8

def test_admin_regenerate_mfa_wrong_password(client, admin_user, db):
    """Admin must provide correct password to regenerate MFA."""
    with client.application.app_context():
        target = User(username='target_user2', role=User.ROLE_SETTER_A)
        target.set_password('Target@123')
        db.session.add(target)
        db.session.commit()
        target_id = target.id
        
    login(client, 'admin', 'Admin@123')
    
    resp = client.post(f'/admin/user/{target_id}/regenerate_mfa', data={
        'admin_password': 'wrong'
    })
    assert resp.status_code == 401
    assert b'Incorrect admin password' in resp.data

def test_non_admin_cannot_regenerate_mfa(client, db):
    """Non-admins get 403 on regenerate route."""
    with client.application.app_context():
        setter = User(username='setter1', role=User.ROLE_SETTER_A)
        setter.set_password('Setter@123')
        db.session.add(setter)
        db.session.commit()
        setter_id = setter.id
        
    login(client, 'setter1', 'Setter@123')
    
    resp = client.get(f'/admin/user/{setter_id}/regenerate_mfa')
    assert resp.status_code == 403
