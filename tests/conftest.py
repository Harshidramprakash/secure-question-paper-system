"""Pytest fixtures for the SQPAS test suite."""
# pyrefly: ignore [missing-import]
import pytest
# pyrefly: ignore [missing-import]
import pyotp

from app import create_app
from app.extensions import db as _db
from app.models.user import User


@pytest.fixture(scope='session')
def app():
    """Create the Flask application configured for testing."""
    app = create_app('testing')
    yield app


@pytest.fixture(scope='function')
def db(app):
    """Provide a clean database for each test function."""
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.rollback()
        _db.drop_all()


@pytest.fixture(scope='function')
def client(app, db):
    """Provide a Flask test client with a clean database."""
    with app.test_client() as client:
        with app.app_context():
            yield client


def _create_user(db_session, username, password, role, mfa_enabled=False):
    """Helper to create a test user."""
    mfa_secret = pyotp.random_base32() if mfa_enabled else None
    user = User(
        username=username,
        role=role,
        mfa_enabled=mfa_enabled,
        mfa_secret=mfa_secret,
        is_active=True,
    )
    user.set_password(password)
    db_session.session.add(user)
    db_session.session.commit()
    return user


@pytest.fixture
def setter_a(db):
    """Create Question Setter A user."""
    return _create_user(db, 'setter_a', 'SetterA@123', User.ROLE_SETTER_A)


@pytest.fixture
def setter_b(db):
    """Create Question Setter B user."""
    return _create_user(db, 'setter_b', 'SetterB@123', User.ROLE_SETTER_B)


@pytest.fixture
def admin_user(db):
    """Create Administrator user."""
    return _create_user(db, 'admin', 'Admin@123', User.ROLE_ADMIN)


@pytest.fixture
def officer_user(db):
    """Create Examination Officer user."""
    return _create_user(db, 'officer', 'Officer@123', User.ROLE_OFFICER)


@pytest.fixture
def mfa_admin(db):
    """Create Administrator user with MFA enabled."""
    return _create_user(db, 'mfa_admin', 'Admin@123', User.ROLE_ADMIN, mfa_enabled=True)


def login(client, username, password):
    """Helper: post login credentials and return the response."""
    return client.post('/auth/login', data={
        'username': username,
        'password': password,
    }, follow_redirects=True)
