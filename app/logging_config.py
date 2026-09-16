"""Production-safe logging configuration for SQPAS.

Provides structured console logging suitable for AWS CloudWatch collection.
Filters prevent sensitive data (passwords, keys, secrets) from appearing in logs.

Usage:
    Called automatically by the app factory during create_app().
"""
import logging
import re
import sys


# Patterns that must NEVER appear in log output
_SENSITIVE_PATTERNS = re.compile(
    r'(password|passwd|secret_key|encryption_key|mfa_secret|totp|'
    r'aws_secret_access_key|private_key|session_cookie|'
    r'BEGIN\s+(RSA\s+)?PRIVATE\s+KEY)',
    re.IGNORECASE,
)


class SensitiveDataFilter(logging.Filter):
    """Logging filter that redacts messages containing sensitive patterns.

    This is a safety net — application code should never log secrets in the
    first place, but this filter catches accidental leaks.
    """

    def filter(self, record):
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            if _SENSITIVE_PATTERNS.search(record.msg):
                record.msg = '[REDACTED — message contained sensitive data]'
                record.args = None
        return True


def configure_logging(app):
    """Set up structured logging for the Flask application.

    - Console handler with timestamp, level, module, and message
    - Log level configurable via LOG_LEVEL config/env var
    - Sensitive data filter applied to all handlers
    - Werkzeug request logging preserved

    Args:
        app: The Flask application instance.
    """
    log_level_name = app.config.get('LOG_LEVEL', 'INFO').upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    # Structured format suitable for CloudWatch parsing
    formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%S%z',
    )

    # Console handler (stdout — CloudWatch Logs Agent reads stdout/stderr)
    console_handler = logging.StreamHandler(stream=sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    console_handler.addFilter(SensitiveDataFilter())

    # Configure the root logger
    root_logger = logging.getLogger()
    # Remove existing handlers to avoid duplicate logs
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.setLevel(log_level)

    # Configure the app logger
    app.logger.handlers.clear()
    app.logger.addHandler(console_handler)
    app.logger.setLevel(log_level)
    app.logger.propagate = False

    # Reduce Werkzeug noise in production
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(logging.WARNING if log_level >= logging.INFO else log_level)

    app.logger.info(
        'Logging configured: level=%s, environment=%s',
        log_level_name,
        app.config.get('ENV', 'unknown'),
    )
