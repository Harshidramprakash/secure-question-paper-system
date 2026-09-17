"""Database initialization and demo user seed script.

Usage:
    python seed.py

Creates all database tables and inserts demo users with pre-configured
TOTP MFA secrets. Writes the TOTP setup details and generated passwords
to a local, git-ignored file.
"""
import os
import sys
import secrets

# Ensure the project root is on the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pyotp
from app import create_app
from app.extensions import db
from app.models.user import User


# Demo roles to seed with specified passwords
DEMO_ROLES = [
    ('admin', User.ROLE_ADMIN, 'admin@123'),
    ('officer', User.ROLE_OFFICER, 'officer@123'),
    ('setter_a', User.ROLE_SETTER_A, 'setter@123'),
    ('setter_b', User.ROLE_SETTER_B, 'setterb@123'),
]


def seed_database():
    """Drop and recreate all tables, then insert demo users."""
    app = create_app('development')

    with app.app_context():
        print('[*] Dropping existing tables...')
        db.drop_all()

        print('[*] Creating tables...')
        db.create_all()

        print('[*] Seeding demo users...')
        
        credentials_output = []
        credentials_output.append('=' * 70)
        credentials_output.append(f'  {"Username":<12} {"Password":<16} {"Role":<22} {"MFA Secret"}')
        credentials_output.append('=' * 70)

        for username, role, password in DEMO_ROLES:
            
            # Generate a TOTP secret for MFA
            mfa_secret = pyotp.random_base32()

            user = User(
                username=username,
                role=role,
                mfa_enabled=True,
                mfa_secret=mfa_secret,
                is_active=True,
            )
            user.set_password(password)
            db.session.add(user)

            credentials_output.append(
                f'  {username:<12} {password:<16} {user.role_display:<22} {mfa_secret}'
            )

        db.session.commit()
        
        credentials_output.append('=' * 70)
        credentials_output.append('\n[i] MFA Setup Instructions:')
        credentials_output.append('    1. Install an authenticator app (Google Authenticator, Authy, etc.)')
        credentials_output.append('    2. Add a new account using the MFA Secret shown above.')
        credentials_output.append('    3. Or generate a current TOTP code using:')
        credentials_output.append('       python -c "import pyotp; print(pyotp.TOTP(\'<MFA_SECRET>\').now())"')

        credentials_text = '\n'.join(credentials_output)
        
        # Write to local file instead of printing
        cred_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.demo_credentials.txt')
        with open(cred_file, 'w') as f:
            f.write(credentials_text)

        print('[OK] Database seeded successfully!')
        print(f'[!] Demo credentials and MFA secrets have been written to:')
        print(f'    {cred_file}')
        print('[!] WARNING: Read this file to get your access details, then DELETE IT securely.')
        
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        if db_uri and db_uri.startswith('sqlite:'):
            print(f'[i] SQLite database location: {app.instance_path}/app.db')
        else:
            print('[i] PostgreSQL database is configured and seeded.')
            
        print('[i] Run the app with: python run.py')
        print()


if __name__ == '__main__':
    seed_database()
