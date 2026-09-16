"""Gunicorn configuration for production deployment on AWS EC2.

Usage:
    gunicorn wsgi:app --config gunicorn.conf.py

Environment variables:
    LOG_LEVEL  — Gunicorn log level (default: info)
    PORT       — Bind port (default: 8000)
    WEB_CONCURRENCY — Number of workers (default: auto-calculated)
"""
import multiprocessing
import os

# --- Bind ---
_port = os.environ.get('PORT', '8000')
bind = f'0.0.0.0:{_port}'

# --- Workers ---
# For a college demo EC2 instance, cap at 4 workers.
# Production recommendation: (2 * CPU cores) + 1
_default_workers = min(multiprocessing.cpu_count() * 2 + 1, 4)
workers = int(os.environ.get('WEB_CONCURRENCY', _default_workers))

# --- Worker class ---
worker_class = 'sync'

# --- Timeouts ---
timeout = 120          # Kill workers that are silent for 120 seconds
graceful_timeout = 30  # Time for workers to finish serving requests during restart
keepalive = 5          # Keep-alive connections timeout

# --- Logging ---
# Logs go to stdout/stderr — CloudWatch Logs Agent or journald collects them
accesslog = '-'   # stdout
errorlog = '-'    # stderr
loglevel = os.environ.get('LOG_LEVEL', 'info').lower()

# --- Security ---
# Limit request sizes to prevent abuse
limit_request_line = 8190
limit_request_fields = 100
limit_request_field_size = 8190

# --- Process naming ---
proc_name = 'sqpas-gunicorn'

# --- Preload ---
# Preload the app to share memory between workers (reduces RAM usage)
preload_app = True
