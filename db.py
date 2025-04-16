"""
Simple re-export of SQLAlchemy db instance to avoid circular imports.
"""
import os
import logging
from flask_sqlalchemy import SQLAlchemy

# Initialize SQLAlchemy
db = SQLAlchemy()

# Log the database connection
if os.environ.get('DATABASE_URL'):
    logging.info("Using PostgreSQL database")
else:
    logging.info("Using SQLite database")