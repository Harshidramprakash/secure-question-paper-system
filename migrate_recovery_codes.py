"""Safe migration script to create the new recovery_codes table.

This script uses SQLAlchemy to create ONLY the recovery_codes table,
ensuring that existing tables and data (users, papers, etc.) are untouched.
"""
import os
import sys
import logging

# Ensure the app can be imported
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app
from app.extensions import db
from app.models.recovery_code import RecoveryCode
from sqlalchemy import inspect

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def run_migration():
    """Create the recovery_codes table safely."""
    # Use the production config if available, fallback to development
    env = os.environ.get('FLASK_ENV', 'development')
    app = create_app(env)
    
    with app.app_context():
        engine = db.engine
        inspector = inspect(engine)
        
        # Check if the table already exists
        if 'recovery_codes' in inspector.get_table_names():
            logging.info("Table 'recovery_codes' already exists. Nothing to do.")
            return

        logging.info("Table 'recovery_codes' not found. Creating it now...")
        
        # Safely create only the RecoveryCode table
        RecoveryCode.__table__.create(engine)
        
        # Verify creation
        if 'recovery_codes' in inspector.get_table_names():
            logging.info("Successfully created 'recovery_codes' table!")
        else:
            logging.error("Failed to create 'recovery_codes' table.")
            sys.exit(1)

if __name__ == '__main__':
    run_migration()
