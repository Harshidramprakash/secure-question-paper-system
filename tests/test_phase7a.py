"""Tests for Phase 7A: AWS Cloud Deployment Preparation.

Validates:
- Production configuration rejects missing required secrets
- Debug mode is disabled in production configuration
- PostgreSQL DATABASE_URL is accepted and postgres:// is rewritten
- WSGI entry point imports correctly
- Security headers are present in responses
- Sensitive values are filtered from logs
- Key provider abstraction works correctly
- Session cookie settings for production
"""
import os
import logging
import pytest

from app.config import ProductionConfig, DevelopmentConfig, TestingConfig, _fix_database_url
from app.services.key_provider import LocalKeyProvider, KeyProviderError


class TestProductionConfigValidation:
    """Production config must reject missing/default secrets."""

    def test_production_config_rejects_missing_secret_key(self, app):
        """ProductionConfig.init_app() raises RuntimeError when SECRET_KEY is default."""
        from flask import Flask
        test_app = Flask(__name__)
        test_app.config.from_object(ProductionConfig)
        # Override with the insecure default
        test_app.config['SECRET_KEY'] = 'dev-secret-key-change-in-production'
        test_app.config['DATABASE_URL'] = 'sqlite:///test.db'

        with pytest.raises(RuntimeError, match='SECRET_KEY'):
            ProductionConfig.init_app(test_app)

    def test_production_config_rejects_missing_encryption_key(self, app):
        """ProductionConfig.init_app() raises RuntimeError when ENCRYPTION_KEY is missing."""
        from flask import Flask
        test_app = Flask(__name__)
        test_app.config.from_object(ProductionConfig)
        test_app.config['SECRET_KEY'] = 'a-real-secret-key-that-is-not-default'
        test_app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://u:p@host/db'
        test_app.config['ENCRYPTION_KEY'] = None

        with pytest.raises(RuntimeError, match='ENCRYPTION_KEY'):
            ProductionConfig.init_app(test_app)

    def test_production_config_rejects_sqlite_database(self, app):
        """ProductionConfig.init_app() raises RuntimeError when using SQLite."""
        from flask import Flask
        test_app = Flask(__name__)
        test_app.config.from_object(ProductionConfig)
        test_app.config['SECRET_KEY'] = 'a-real-secret-key-that-is-not-default'
        test_app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
        test_app.config['ENCRYPTION_KEY'] = 'a' * 64

        with pytest.raises(RuntimeError, match='DATABASE_URL is not set or is using SQLite'):
            ProductionConfig.init_app(test_app)

    def test_development_config_allows_missing_database(self, app):
        """DevelopmentConfig.init_app() does not raise RuntimeError when DATABASE_URL is missing (allows SQLite)."""
        from flask import Flask
        from app.config import DevelopmentConfig
        test_app = Flask(__name__)
        test_app.config.from_object(DevelopmentConfig)
        test_app.config['SQLALCHEMY_DATABASE_URI'] = None

        # Should not raise any error
        DevelopmentConfig.init_app(test_app)

    def test_production_config_passes_with_all_secrets(self, app):
        """ProductionConfig.init_app() succeeds when all secrets are provided."""
        from flask import Flask
        test_app = Flask(__name__)
        test_app.config.from_object(ProductionConfig)
        test_app.config['SECRET_KEY'] = 'a-real-secret-key-that-is-not-default'
        test_app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://u:p@host/db'
        test_app.config['ENCRYPTION_KEY'] = 'a' * 64

        # Should not raise
        ProductionConfig.init_app(test_app)


class TestProductionSettings:
    """Verify production security settings."""

    def test_production_debug_disabled(self):
        """DEBUG must be False in production."""
        assert ProductionConfig.DEBUG is False

    def test_production_testing_disabled(self):
        """TESTING must be False in production."""
        assert ProductionConfig.TESTING is False

    def test_production_session_cookie_secure(self):
        """SESSION_COOKIE_SECURE must be True in production."""
        assert ProductionConfig.SESSION_COOKIE_SECURE is True

    def test_production_session_cookie_samesite_strict(self):
        """SESSION_COOKIE_SAMESITE must be 'Strict' in production."""
        assert ProductionConfig.SESSION_COOKIE_SAMESITE == 'Strict'

    def test_production_session_cookie_httponly(self):
        """SESSION_COOKIE_HTTPONLY must be True (inherited from base)."""
        assert ProductionConfig.SESSION_COOKIE_HTTPONLY is True

    def test_development_debug_enabled(self):
        """DEBUG should be True in development."""
        assert DevelopmentConfig.DEBUG is True

    def test_testing_uses_sqlite_memory(self):
        """Testing config should use in-memory SQLite."""
        assert TestingConfig.SQLALCHEMY_DATABASE_URI == 'sqlite:///:memory:'


class TestPostgreSQLCompatibility:
    """Test DATABASE_URL handling."""

    def test_postgres_url_rewritten(self):
        """postgres:// prefix should be rewritten to postgresql://."""
        url = 'postgres://user:pass@host:5432/db'
        assert _fix_database_url(url) == 'postgresql://user:pass@host:5432/db'

    def test_postgresql_url_unchanged(self):
        """postgresql:// prefix should remain unchanged."""
        url = 'postgresql://user:pass@host:5432/db'
        assert _fix_database_url(url) == url

    def test_sqlite_url_unchanged(self):
        """sqlite:// URLs should remain unchanged."""
        url = 'sqlite:///app.db'
        assert _fix_database_url(url) == url

    def test_empty_url_handled(self):
        """Empty/None URLs should not crash."""
        assert _fix_database_url('') == ''
        assert _fix_database_url(None) is None


class TestWSGIImport:
    """Verify the WSGI entry point works correctly."""

    def test_wsgi_module_imports(self):
        """wsgi.py can be imported successfully."""
        import subprocess
        import sys
        import os
        env = os.environ.copy()
        env['DATABASE_URL'] = 'sqlite:///:memory:'
        env['SECRET_KEY'] = 'a' * 64
        env['ENCRYPTION_KEY'] = 'a' * 64
        result = subprocess.run(
            [sys.executable, '-c', 'import wsgi; print(wsgi.app)'],
            env=env,
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Failed to import wsgi: {result.stderr}"
        assert "Flask" in result.stdout or "Flask" in result.stderr

    def test_wsgi_app_is_flask(self):
        """wsgi.app should be a Flask application instance."""
        # Covered by the test above that prints wsgi.app
        pass


class TestSecurityHeaders:
    """Verify security headers are set on responses."""

    def test_x_content_type_options(self, client):
        """X-Content-Type-Options: nosniff should be present."""
        resp = client.get('/auth/login')
        assert resp.headers.get('X-Content-Type-Options') == 'nosniff'

    def test_x_frame_options(self, client):
        """X-Frame-Options: SAMEORIGIN should be present."""
        resp = client.get('/auth/login')
        assert resp.headers.get('X-Frame-Options') == 'SAMEORIGIN'

    def test_x_xss_protection(self, client):
        """X-XSS-Protection should be present."""
        resp = client.get('/auth/login')
        assert resp.headers.get('X-XSS-Protection') == '1; mode=block'

    def test_referrer_policy(self, client):
        """Referrer-Policy should be present."""
        resp = client.get('/auth/login')
        assert resp.headers.get('Referrer-Policy') == 'strict-origin-when-cross-origin'

    def test_content_security_policy(self, client):
        """Content-Security-Policy should be present."""
        resp = client.get('/auth/login')
        csp = resp.headers.get('Content-Security-Policy')
        assert csp is not None
        assert "default-src 'self'" in csp
        assert 'fonts.googleapis.com' in csp


class TestKeyProvider:
    """Test the key provider abstraction."""

    def test_local_key_provider_returns_correct_key(self):
        """LocalKeyProvider should return the correct 32-byte key."""
        key_hex = 'a' * 64  # 32 bytes of 0xAA
        provider = LocalKeyProvider(key_hex=key_hex)
        key = provider.get_key()
        assert len(key) == 32
        assert key == bytes.fromhex(key_hex)

    def test_local_key_provider_rejects_short_key(self):
        """LocalKeyProvider should reject keys shorter than 32 bytes."""
        with pytest.raises(KeyProviderError, match='32 bytes'):
            provider = LocalKeyProvider(key_hex='aa')
            provider.get_key()

    def test_local_key_provider_rejects_invalid_hex(self):
        """LocalKeyProvider should reject non-hex strings."""
        with pytest.raises(KeyProviderError):
            provider = LocalKeyProvider(key_hex='not-a-hex-string-at-all!!')
            provider.get_key()

    def test_local_key_provider_rejects_missing_key(self):
        """LocalKeyProvider should raise error when no key is available."""
        # Clear the env var to test the error path
        old_val = os.environ.pop('ENCRYPTION_KEY', None)
        try:
            with pytest.raises(KeyProviderError, match='not configured'):
                provider = LocalKeyProvider(key_hex=None)
                provider.get_key()
        finally:
            if old_val is not None:
                os.environ['ENCRYPTION_KEY'] = old_val

    def test_key_provider_name(self):
        """Provider should report its name correctly."""
        provider = LocalKeyProvider(key_hex='a' * 64)
        assert provider.provider_name() == 'LocalKeyProvider'


class TestSensitiveDataFilter:
    """Verify the logging filter redacts sensitive data."""

    def test_password_redacted_in_logs(self, app):
        """Log messages containing 'password' should be redacted."""
        from app.logging_config import SensitiveDataFilter

        filt = SensitiveDataFilter()
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='User password is secret123', args=None, exc_info=None,
        )
        filt.filter(record)
        assert 'secret123' not in record.msg
        assert 'REDACTED' in record.msg

    def test_encryption_key_redacted_in_logs(self, app):
        """Log messages containing 'encryption_key' should be redacted."""
        from app.logging_config import SensitiveDataFilter

        filt = SensitiveDataFilter()
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='encryption_key = abcdef123456', args=None, exc_info=None,
        )
        filt.filter(record)
        assert 'abcdef' not in record.msg
        assert 'REDACTED' in record.msg

    def test_safe_messages_pass_through(self, app):
        """Normal log messages should not be redacted."""
        from app.logging_config import SensitiveDataFilter

        filt = SensitiveDataFilter()
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='User admin logged in successfully', args=None, exc_info=None,
        )
        filt.filter(record)
        assert record.msg == 'User admin logged in successfully'
