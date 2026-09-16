"""Flask application configuration.

Supports development, testing, staging, and production environments.
Production configuration validates that all required secrets are provided
via environment variables and fails fast with a clear error if any are missing.
"""
import os
from datetime import timedelta


class BaseConfig:
    """Base configuration shared by all environments."""

    # --- Flask core ---
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

    # --- Database (SQLite default for local development) ---
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Session security ---
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)

    # --- CSRF protection ---
    WTF_CSRF_ENABLED = True

    # --- AES-256 encryption key (hex-encoded, 64 hex chars = 32 bytes) ---
    ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY')

    # --- Timezone for release scheduling ---
    APP_TIMEZONE = os.environ.get('APP_TIMEZONE', 'Asia/Kolkata')

    # --- Logging ---
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

    # --- Proxy ---
    BEHIND_PROXY = os.environ.get('BEHIND_PROXY', '').lower() in ('true', '1', 'yes')

    @classmethod
    def init_app(cls, app):
        """Optional hook for environment-specific initialization."""
        pass


class DevelopmentConfig(BaseConfig):
    """Development configuration."""
    DEBUG = True
    SESSION_COOKIE_SECURE = False  # Allow HTTP in development
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'DEBUG')


class TestingConfig(BaseConfig):
    """Testing configuration."""
    TESTING = True
    DEBUG = True
    SESSION_COOKIE_SECURE = False
    WTF_CSRF_ENABLED = False  # Disable CSRF in tests for convenience
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    ENCRYPTION_KEY = 'a' * 64  # 32-byte test key (hex-encoded)
    SECRET_KEY = 'test-secret-key'
    LOG_LEVEL = 'WARNING'


class ProductionConfig(BaseConfig):
    """Production configuration — requires proper env vars.

    The application will refuse to start if critical secrets are missing.
    This prevents accidental deployment with insecure defaults.
    """
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = 'Strict'
    PREFERRED_URL_SCHEME = 'https'

    # PostgreSQL connection pool settings (ignored for SQLite)
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 5,
        'pool_recycle': 300,
        'pool_pre_ping': True,
        'max_overflow': 10,
    }

    @classmethod
    def init_app(cls, app):
        """Validate that all required production secrets are configured."""
        errors = []

        secret_key = app.config.get('SECRET_KEY', '')
        if not secret_key or secret_key == 'dev-secret-key-change-in-production':
            errors.append(
                'SECRET_KEY is not set or is using the insecure default. '
                'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
            )

        db_url = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        if not db_url or db_url.startswith('sqlite:'):
            errors.append(
                'DATABASE_URL is not set or is using SQLite. '
                'Set DATABASE_URL to a PostgreSQL connection string for production.'
            )

        enc_key = app.config.get('ENCRYPTION_KEY')
        if not enc_key:
            errors.append(
                'ENCRYPTION_KEY is not set. '
                'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
            )

        if errors:
            error_msg = (
                '\n\n*** PRODUCTION CONFIGURATION ERROR ***\n'
                + '\n'.join(f'  - {e}' for e in errors)
                + '\n\nThe application cannot start safely without these settings.\n'
            )
            raise RuntimeError(error_msg)


# Alias for staging (same validation as production)
StagingConfig = ProductionConfig


def _fix_database_url(url):
    """Fix common DATABASE_URL format issues.

    Some platforms (e.g. Heroku, older AWS docs) use 'postgres://' which
    SQLAlchemy 1.4+ no longer accepts. Rewrite to 'postgresql://'.
    """
    if url and url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    return url


# Apply URL fix to all configs that read DATABASE_URL
_raw_url = os.environ.get('DATABASE_URL', '')
if _raw_url:
    _fixed_url = _fix_database_url(_raw_url)
    BaseConfig.SQLALCHEMY_DATABASE_URI = _fixed_url


config_map = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'staging': StagingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
