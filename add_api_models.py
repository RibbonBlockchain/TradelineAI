"""
Migration script to add API models for external platform access.
This adds:
1. APIKey table
2. APIUsage table
3. APISubscription table
"""

import os
import sys
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, Float, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# Create a direct SQLAlchemy engine connection to the database
def create_db_connection():
    """Create a direct SQLAlchemy engine connection to the database"""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("Error: DATABASE_URL environment variable not set")
        sys.exit(1)
    
    # Create SQLAlchemy engine
    engine = create_engine(database_url)
    
    # Create session
    Session = sessionmaker(bind=engine)
    session = Session()
    
    return engine, session

# Define the base class
Base = declarative_base()

# Define API models
class APIKey(Base):
    """API Key model for external platform authentication"""
    __tablename__ = 'api_key'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    key = Column(String(64), unique=True, nullable=False)
    tier = Column(String(32), nullable=False, default='basic')
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    subscription_id = Column(String(64))
    last_used_at = Column(DateTime)

class APIUsage(Base):
    """API Usage tracking model"""
    __tablename__ = 'api_usage'
    
    id = Column(Integer, primary_key=True)
    api_key_id = Column(Integer, ForeignKey('api_key.id'), nullable=False)
    endpoint = Column(String(256), nullable=False)
    method = Column(String(10), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    response_status = Column(Integer)
    response_time_ms = Column(Float)

class APISubscription(Base):
    """API Subscription model for tracking subscription status"""
    __tablename__ = 'api_subscription'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    subscription_id = Column(String(64), unique=True, nullable=False)
    tier = Column(String(32), nullable=False, default='basic')
    status = Column(String(32), nullable=False, default='active')
    created_at = Column(DateTime, default=datetime.utcnow)
    current_period_start = Column(DateTime)
    current_period_end = Column(DateTime)
    canceled_at = Column(DateTime)
    subscription_metadata = Column(Text)

def add_api_models():
    """Add API models to the database"""
    engine, session = create_db_connection()
    
    # Create inspector to check if tables exist
    from sqlalchemy import inspect
    inspector = inspect(engine)
    
    # Check if tables already exist
    if 'api_key' not in inspector.get_table_names():
        APIKey.__table__.create(engine)
        print("Created APIKey table")
    else:
        print("APIKey table already exists")
    
    if 'api_usage' not in inspector.get_table_names():
        APIUsage.__table__.create(engine)
        print("Created APIUsage table")
    else:
        print("APIUsage table already exists")
    
    if 'api_subscription' not in inspector.get_table_names():
        APISubscription.__table__.create(engine)
        print("Created APISubscription table")
    else:
        print("APISubscription table already exists")
    
    # Close session
    session.close()

def run_migration():
    """Run the database migration to add API models"""
    add_api_models()
    print("API models migration completed successfully")

if __name__ == "__main__":
    run_migration()