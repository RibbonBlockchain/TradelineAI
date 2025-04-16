import sys
import os

# Set the application directory to the current directory
sys.path.insert(0, os.path.abspath('.'))

from app import app, db
from sqlalchemy import Column, Text, text

def add_description_column():
    """Add description column to the tradeline table"""
    with app.app_context():
        # Add description column using db session execute
        engine = db.engine
        inspector = db.inspect(engine)
        
        # Check if the column already exists
        columns = [col['name'] for col in inspector.get_columns('tradeline')]
        if 'description' not in columns:
            print("Adding description column to tradeline table...")
            with engine.connect() as conn:
                conn.execute(text('ALTER TABLE tradeline ADD COLUMN description TEXT'))
                conn.commit()
            print("Description column added successfully.")
        else:
            print("Description column already exists in tradeline table.")

if __name__ == "__main__":
    add_description_column()