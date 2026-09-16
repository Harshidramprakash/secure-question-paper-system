"""Flask application factory.

Creates and configures the SQPAS Flask application with:
- Environment-specific configuration (dev/test/staging/production)
- Production secret validation
- Security headers
- Structured logging
- Proxy support when behind Nginx
"""
import os
import logging
from flask import Flask
from dotenv import load_dotenv

from .config import config_map
from .extensions import db, login_manager, csrf
from .logging_config import configure_logging

logger = logging.getLogger(__name__)


def create_app(config_name=None):
    """Create and configure the Flask application.

    Args:
        config_name: One of 'development', 'testing', 'staging', 'production'.
                     Defaults to FLASK_ENV or 'development'.
    """
    # Load .env file if it exists
    load_dotenv()

    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(
        __name__,
        instance_relative_config=True,
    )

    config_class = config_map.get(config_name, config_map['default'])
    app.config.from_object(config_class)

    # Run environment-specific initialization (e.g. production secret validation)
    if hasattr(config_class, 'init_app'):
        config_class.init_app(app)

    # Configure structured logging
    configure_logging(app)

    # Ensure the instance folder exists (for SQLite DB in development)
    os.makedirs(app.instance_path, exist_ok=True)

    # Apply ProxyFix when running behind a reverse proxy (Nginx)
    if app.config.get('BEHIND_PROXY'):
        try:
            from werkzeug.middleware.proxy_fix import ProxyFix
            app.wsgi_app = ProxyFix(
                app.wsgi_app,
                x_for=1,       # Trust X-Forwarded-For (1 proxy)
                x_proto=1,     # Trust X-Forwarded-Proto
                x_host=1,      # Trust X-Forwarded-Host
                x_prefix=1,    # Trust X-Forwarded-Prefix
            )
            logger.info('ProxyFix applied (BEHIND_PROXY=true)')
        except ImportError:
            logger.warning('ProxyFix requested but werkzeug.middleware.proxy_fix not available')

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Register user loader
    from .models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)

    # Register additional blueprints (added in later phases)
    _register_optional_blueprints(app)

    # Register template utilities
    _register_template_helpers(app)

    # Register security headers
    _register_security_headers(app)

    # Create database tables
    with app.app_context():
        from . import models  # noqa: F401 — ensure all models are imported
        db.create_all()

    logger.info(
        'SQPAS application created: config=%s, debug=%s',
        config_name,
        app.debug,
    )

    return app


def _register_security_headers(app):
    """Add security headers to all responses.

    These headers protect against common web vulnerabilities:
    - X-Content-Type-Options: Prevents MIME-type sniffing
    - X-Frame-Options: Prevents clickjacking
    - X-XSS-Protection: Legacy XSS protection for older browsers
    - Referrer-Policy: Controls referrer information leakage
    - Content-Security-Policy: Controls resource loading sources
    """

    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # Content-Security-Policy — allow Google Fonts CDN used by base.html
        # and inline styles used in templates
        if 'Content-Security-Policy' not in response.headers:
            response.headers['Content-Security-Policy'] = (
                "default-src 'self'; "
                "style-src 'self' https://fonts.googleapis.com 'unsafe-inline'; "
                "font-src 'self' https://fonts.gstatic.com; "
                "script-src 'self'; "
                "img-src 'self' data:; "
                "connect-src 'self'; "
                "frame-ancestors 'self'"
            )

        return response


def _register_template_helpers(app):
    """Register Jinja2 filters and context processors."""

    @app.template_filter('has_endpoint')
    def has_endpoint(endpoint_name):
        """Check whether a Flask endpoint exists (for graceful nav links)."""
        from flask import current_app
        return endpoint_name in current_app.view_functions

    @app.context_processor
    def inject_globals():
        """Inject utility variables into all templates."""
        from flask import session
        return {
            'mfa_verified': session.get('mfa_verified', False),
        }


def _register_optional_blueprints(app):
    """Register blueprints added in later phases — silently skip if missing."""
    optional = [
        ('app.routes.setter', 'setter_bp'),
        ('app.routes.admin', 'admin_bp'),
        ('app.routes.officer', 'officer_bp'),
        ('app.routes.audit', 'audit_bp'),
    ]
    import importlib
    for module_path, bp_name in optional:
        try:
            module = importlib.import_module(module_path)
            bp = getattr(module, bp_name, None)
            if bp:
                app.register_blueprint(bp)
        except (ImportError, ModuleNotFoundError):
            pass  # Blueprint not yet implemented
