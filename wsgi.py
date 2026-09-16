"""WSGI entry point for production deployment.

Used by Gunicorn (or any WSGI server) to serve the SQPAS application.

Usage:
    gunicorn wsgi:app --config gunicorn.conf.py

This module MUST NOT enable debug mode or call app.run().
"""
from app import create_app

app = create_app()
