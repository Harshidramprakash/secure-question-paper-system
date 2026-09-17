"""MFA and recovery code generation services."""
import pyotp
import qrcode
import io
import base64
import secrets
import string
from werkzeug.security import generate_password_hash
from flask import current_app

from ..extensions import db
from ..models.user import User
from ..models.recovery_code import RecoveryCode

def generate_recovery_codes(user_id, count=8):
    """Generate and store hashed recovery codes for a user.
    Returns the plaintext codes so they can be shown once.
    """
    # Delete old codes
    RecoveryCode.query.filter_by(user_id=user_id).delete()
    
    alphabet = string.ascii_uppercase + string.digits
    plaintext_codes = []
    
    for _ in range(count):
        # Generate code in format XXXX-XXXX
        part1 = ''.join(secrets.choice(alphabet) for i in range(4))
        part2 = ''.join(secrets.choice(alphabet) for i in range(4))
        code = f"{part1}-{part2}"
        plaintext_codes.append(code)
        
        # Hash code for storage
        code_hash = generate_password_hash(code, method='scrypt', salt_length=16)
        
        # Save to DB
        rc = RecoveryCode(user_id=user_id, code_hash=code_hash)
        db.session.add(rc)
        
    db.session.commit()
    return plaintext_codes

def generate_mfa_qr_b64(user, secret):
    """Generate a base64-encoded PNG of the TOTP provisioning QR code."""
    # issuer_name should be loaded from config if possible, fallback to 'SQPAS'
    issuer_name = 'SQPAS'
    
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(name=user.username, issuer_name=issuer_name)
    
    img = qrcode.make(provisioning_uri)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    
    return base64.b64encode(buf.getvalue()).decode('utf-8')
