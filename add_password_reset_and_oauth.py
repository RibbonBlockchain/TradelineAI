"""
Migration script to add password reset and OAuth fields to User table.
"""
import logging
import os
from datetime import datetime
from sqlalchemy import create_engine, text
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

def create_db_connection():
    """Create a direct SQLAlchemy engine connection to the database"""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logging.error("DATABASE_URL environment variable not set")
        return None
    
    try:
        engine = create_engine(db_url)
        conn = engine.connect()
        logging.info("Successfully connected to database")
        return conn
    except Exception as e:
        logging.error(f"Failed to connect to database: {e}")
        return None

def add_password_reset_and_oauth_columns():
    """Add password reset and OAuth columns to the User table"""
    # Connect to DB
    logging.info("Adding password reset and OAuth columns to User table...")
    
    # Create direct connection to database
    conn = create_db_connection()
    if not conn:
        return False
    
    try:
        # Execute the ALTER TABLE commands
        commands = [
            # Password reset fields
            "ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS reset_password_token VARCHAR(128)",
            "ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS reset_password_expires TIMESTAMP",
            # OAuth fields
            "ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS google_id VARCHAR(128) UNIQUE",
            "ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS is_oauth_user BOOLEAN DEFAULT FALSE",
            # Create index on reset_password_token
            "CREATE INDEX IF NOT EXISTS ix_user_reset_password_token ON \"user\" (reset_password_token)"
        ]
        
        for command in commands:
            conn.execute(text(command))
        
        conn.commit()
        logging.info("Added password reset and OAuth columns to User table successfully")
        return True
    except Exception as e:
        conn.rollback()
        logging.error(f"Failed to add password reset and OAuth columns: {e}")
        return False
    finally:
        conn.close()

def run_migration():
    """Run the database migration to add password reset and OAuth functionality to Users"""
    logging.basicConfig(level=logging.INFO)
    
    # Add columns
    if add_password_reset_and_oauth_columns():
        logging.info("Migration completed successfully")
    else:
        logging.error("Migration failed")

if __name__ == "__main__":
    run_migration()