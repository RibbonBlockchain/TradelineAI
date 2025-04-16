"""
Migration script to add A2A protocol integration fields to AIAgent table.
"""

import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Boolean, String, DateTime, Integer, Text, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Create a direct connection to the database
def create_db_connection():
    """Create a direct SQLAlchemy engine connection to the database"""
    database_url = os.environ.get('DATABASE_URL')
    engine = create_engine(database_url)
    return engine, sessionmaker(bind=engine)()

def add_a2a_columns():
    """Add A2A protocol integration columns to the AIAgent table"""
    engine, session = create_db_connection()
    
    # Check if the columns already exist
    inspector = inspect(engine)
    columns = [column['name'] for column in inspector.get_columns('ai_agent')]
    
    columns_to_add = []
    if 'a2a_enabled' not in columns:
        columns_to_add.append("a2a_enabled BOOLEAN DEFAULT FALSE")
    
    if 'bns_identifier' not in columns:
        columns_to_add.append("bns_identifier VARCHAR(256) UNIQUE")
    
    if 'a2a_metadata' not in columns:
        columns_to_add.append("a2a_metadata TEXT")
    
    if 'a2a_last_seen' not in columns:
        columns_to_add.append("a2a_last_seen TIMESTAMP")
    
    if 'a2a_interaction_count' not in columns:
        columns_to_add.append("a2a_interaction_count INTEGER DEFAULT 0")
    
    if 'purpose_code' not in columns:
        columns_to_add.append("purpose_code VARCHAR(20)")
    
    if 'entity_code' not in columns:
        columns_to_add.append("entity_code VARCHAR(50)")
    
    # Add the new columns if they don't exist
    if columns_to_add:
        for column_def in columns_to_add:
            try:
                # Add column to the table
                sql = text(f"ALTER TABLE ai_agent ADD COLUMN {column_def}")
                session.execute(sql)
                print(f"Added column {column_def.split()[0]} to AIAgent table")
            except Exception as e:
                print(f"Error adding column {column_def.split()[0]}: {e}")
        
        session.commit()
        print("A2A columns added to AIAgent table")
    else:
        print("All A2A columns already exist in AIAgent table")
    
    session.close()

def run_migration():
    """Run the database migration to add A2A protocol integration fields to AIAgent"""
    try:
        print("Starting A2A protocol integration fields migration...")
        add_a2a_columns()
        print("A2A protocol integration fields migration completed successfully")
        return True
    except Exception as e:
        print(f"Migration failed: {e}")
        return False

if __name__ == "__main__":
    run_migration()